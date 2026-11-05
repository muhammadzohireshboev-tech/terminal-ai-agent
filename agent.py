"""Terminal AI agent: OpenRouter orqali model + fayl asboslar (read/write/list)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent
MAX_TOOL_ROUNDS = 20

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "nvidia/nemotron-3-ultra-550b-a55b:free",
    },
    "radox": {
        "base_url": "https://radoxai.com/v1",
        "key_env": "RADOX_API_KEY",
        "default_model": "",
    },
}

SYSTEM_PROMPT = (
    "Sen terminalda ishlaydigan coding agent'san. Ish papkasi: {root}. "
    "Fayllarni faqat asboslar orqali ko'rasan, o'zing taxmin qilmaysan. "
    "Bir ishni bajarish uchun ketma-ket asbos ishlat: avval o'qi, keyin yoz. "
    "Javobni qisqa va aniq ber, o'zbek tilida izohla."
).format(root=ROOT)


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def safe_path(raw: str) -> Path:
    path = (ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise ValueError(f"yo'l ish papkasidan tashqarida: {raw}")
    return path


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Fayl mazmunini matn sifatida o'qiydi.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Ish papkasiga nisbiy yo'l"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Faylga to'liq mazmun yozadi (kerak bo'lsa papka yaratadi).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ish papkasiga nisbiy yo'l"},
                    "content": {"type": "string", "description": "Yoziladigan to'liq matn"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Papkadagi fayl va papkalarni ro'yxat qiladi.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Nisbiy yo'l, bo'sh bo'lsa ish papkasi"}},
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    try:
        if name == "read_file":
            path = safe_path(args["path"])
            text = path.read_text(encoding="utf-8")
            if len(text) > 60_000:
                text = text[:60_000] + "\n... [qisqartirildi]"
            return text
        if name == "write_file":
            path = safe_path(args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return f"yozildi: {path.relative_to(ROOT)} ({len(args['content'])} belgi)"
        if name == "list_dir":
            path = safe_path(args.get("path") or ".")
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            return "\n".join(f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries) or "papka bo'sh"
    except Exception as exc:  # agent xatoni ko'rib, o'zini tuzatishi uchun
        return f"XATO: {type(exc).__name__}: {exc}"
    return f"XATO: noma'lum asbos {name}"


STATUS_HOOK = None  # GUI shu joyga o'z funksiyasini qo'yadi


def publish(text: str) -> None:
    print(f"\r{text}", end="", file=sys.stderr, flush=True)
    if STATUS_HOOK is not None:
        STATUS_HOOK(text.strip())


@contextmanager
def status(label: str):
    """Buyruq bajarilayotganini bir satrda, soni bilan ko'rsatib turadi."""
    start = time.time()
    stop = threading.Event()

    def line(prefix: str, secs: str) -> str:
        return f"  [{prefix}] {label} ({secs}s)"

    def tick() -> None:
        while not stop.wait(1.0):
            publish(line("bajarilmoqda", f"{time.time() - start:.0f}"))

    publish(line("bajarilmoqda", "0"))
    worker = threading.Thread(target=tick, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join()
        publish(line("bajarildi", f"{time.time() - start:.1f}") + " " * 8)


def shorten(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def chat(client: OpenAI, model: str, messages: list, task: str) -> str:
    for _ in range(MAX_TOOL_ROUNDS):
        with status(f"'{task}' - model o'ylayapti"):
            response = client.chat.completions.create(
                model=model, messages=messages, tools=TOOL_SPECS, temperature=0.2
            )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content or ""

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            preview = shorten(str(args.get("path", "")), 40)
            with status(f"{call.function.name}({preview})"):
                result = run_tool(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

    return "Juda ko'p asbos davri — to'xtatildi."


class ConfigError(RuntimeError):
    pass


def resolve_provider() -> tuple[str, str, str, str]:
    name = os.environ.get("AGENT_PROVIDER", "openrouter").strip().lower()
    conf = PROVIDERS.get(name)
    if conf is None:
        raise ConfigError(f"AGENT_PROVIDER noto'g'ri: {name!r}. Yozish: {', '.join(PROVIDERS)}")
    key = os.environ.get(conf["key_env"], "").strip()
    if not key:
        raise ConfigError(
            f"{conf['key_env']} sozlanmagan. {ROOT / '.env'} fayliga yozing:\n"
            f"  AGENT_PROVIDER={name}\n  {conf['key_env']}=..."
        )
    return name, conf["base_url"], key, os.environ.get("AGENT_MODEL", "").strip() or conf["default_model"]


def connect() -> tuple[str, str, OpenAI]:
    provider, base_url, key, model = resolve_provider()
    if not model:
        raise ConfigError(f"{provider} uchun model kerak. Ro'yxat: python agent.py --models")
    return provider, model, OpenAI(base_url=base_url, api_key=key)


def list_models(base_url: str, key: str) -> None:
    for model in OpenAI(base_url=base_url, api_key=key).models.list().data:
        print(model.id)


def main() -> None:
    load_env()
    try:
        provider, base_url, key, model = resolve_provider()
    except ConfigError as exc:
        sys.exit(str(exc))

    if "--models" in sys.argv:
        try:
            list_models(base_url, key)
        except Exception as exc:
            sys.exit(f"[xato] modellar ro'yxati: {type(exc).__name__}: {str(exc)[:200]}")
        return
    if not model:
        sys.exit(f"{provider} uchun model kerak. Ro'yxat: python agent.py --models")

    client = OpenAI(base_url=base_url, api_key=key)
    messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"Agent tayyor | provayder: {provider} | model: {model} | papka: {ROOT}")
    print("Buyruqlar: /reset - tarixni tozalash, /exit - chiqish\n")

    while True:
        try:
            user = input("siz> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/exit", "/quit"):
            break
        if user == "/reset":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("tarix tozalandi")
            continue
        messages.append({"role": "user", "content": user})
        try:
            answer = chat(client, model, messages, shorten(user))
        except Exception as exc:
            print(f"[xato] {type(exc).__name__}: {str(exc)[:200]}\n")
            continue
        print(f"agent> {answer}\n")


if __name__ == "__main__":
    main()

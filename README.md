# Terminal AI Agent

OpenRouter yoki Radox AI (https://radoxai.com) ga ulangan, fayllarni o'qiy/yoza
oladigan agent. Ikki interfeys: terminal (`agent.py`) va tkinter oynasi (`gui.py`) —
ikkalasi bitta mantikdan foydalanadi.

## Ishga tushirish

```bash
cp .env.example .env      # .env ichiga haqiqiy kalitni yozing
python agent.py           # terminal rejimi
python gui.py             # oyna (GUI) rejimi
```

Yoki muhit o'zgaruvchisi orqali:

```bash
export AGENT_PROVIDER=radox
export RADOX_API_KEY=...
python agent.py
```

Kalit olish: https://openrouter.ai/settings/keys · https://radoxai.com

## Sozlamalar (.env)

| Kalit | Standart qiymat | Izoh |
| --- | --- | --- |
| `AGENT_PROVIDER` | `openrouter` | `openrouter` yoki `radox` |
| `OPENROUTER_API_KEY` | — | `AGENT_PROVIDER=openrouter` bo'lsa kerak |
| `RADOX_API_KEY` | — | `AGENT_PROVIDER=radox` bo'lsa kerak |
| `AGENT_MODEL` | provayder standarti | `nvidia/nemotron-3-ultra-550b-a55b:free`; Radox uchun majburiy |

Model ro'yxatini provayderdan so'rash:

```bash
python agent.py --models     # AGENT_PROVIDER dagi kalit bilan /models ni chop etadi
```

Radox'da model nomi aniq ko'rsatilgan (`.env` da `AGENT_MODEL=` bo'sh bo'lsa agent
ro'yxatni so'raydi). Shu `--models` chiqishidan birini tanlab yozing.

## Agent asboslari

- `read_file(path)` — fayl mazmunini o'qiydi
- `write_file(path, content)` — fayl yozadi, papka kerak bo'lsa yaratadi
- `list_dir(path)` — papka ro'yxati

Barcha yo'llar ish papkasida (`agent.py` yonida) qoladi — undan tashqariga chiqib bo'lmaydi.

## Suhbatda

- `/reset` — tarixni tozalash
- `/exit` — chiqish

Har bir qadam bir satrda jonli ko'rsatiladi (sekund hisoblagichi bilan):

```
  [bajarilmoqda] 'demo.txt mazmunini oqib ber.' - model o'ylayapti (3s)
  [bajarildi]     'demo.txt mazmunini oqib ber.' - model o'ylayapti (4.2s)
  [bajarilmoqda] read_file(demo.txt)
  [bajarildi]     read_file(demo.txt) (0.0s)
```

Model API javobi kechikkanida ham agent "nima qilayotgani ko'rinmaydi" degan
holat bo'lmaydi — qaysi buyruq bajarilayotgani va necha sekund ketgani shu
satrda turadi.

> `.env` da provayderni `radox` ga o'zgartirsangiz, `AGENT_MODEL` ni ham
> almashtiring (OpenRouter nomi Radox'da ishlamaydi). Banner'da qaysi
> provayder/qaysi model ishlatilayotgani yozib chiqadi.

## Oyna (GUI)

```bash
python gui.py
```

- Yuqoridagi panel: provayder, model va ish papkasi
- Markazda suhbat tarixi (`siz>` / `agent>` / `xato>` / `tizim>` rang bilan)
- Pastdagi status satri jonli yangilanadi: qaysi buyruq bajarilayotgani va necha
  sekund ketgani (`[bajarilmoqda] read_file(demo.txt) (1s)`)
- `Yuborish` tugmasi yoki Enter; `Tarixni tozalash` — `/reset` bilan bir xil
- Model so'rovi alohida oqimda (thread) ketadi, shuning uchun oyna "qotmaydi";
  javob kutilib turganda kiritish maydoni bloklanadi

GUI `agent.py` dagi `chat()`, `run_tool()` va `connect()` funksiyalarini chaqiradi —
terminal va oyna bir xil ishlaydi.

## Model tezligi

`nvidia/nemotron-3-ultra-550b-a55b:free` ishonchli, lekin o'ylanadi (~5-20s qadam).
Tezroq variantlar (`cohere/north-mini-code:free`, `nvidia/nemotron-3.5-lightning:free`)
tekshirildi: 1-2s javob beradi, ammo `write_file` chaqiruvini bajarolmay qo'ydi.
Shuning uchun standart — sekinroq, lekin to'g'ri ishlaydigan model.

## Misol

```
siz> demo.txt fayliga bugungi rejamni yoz
  [bajarilmoqda] write_file(demo.txt)
  [bajarildi]     write_file(demo.txt) (0.0s)
agent> demo.txt yaratildi: 3 banddan iborat reja yozildi.
```

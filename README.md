# eeky808

my build logic site or whatever. made this cuz im obsessed with build logic on roblox lol.

live at [eeky808.onrender.com](https://eeky808.onrender.com)

## what is this

a little fastapi site that serves a typewriter for a 16x16 text panel, plus an api for the character table from build logic. built for a panel circuit that hits the api to write text on the panel one char at a time.

## endpoints

### pages

- `GET /` — homepage (typewriter form + api links)
- `GET /docs` — swagger ui, play with everything
- `GET /openapi.json` — the raw spec
- `GET /health` — `{"status": "ok"}`, for uptime monitors

### typewriter

- `POST /api/typewriter` — set the text to type. body: `{"text": "hello"}`
- `GET /api/typewriter/current` — next char's 8-bit value, advances one step per GET
- `GET /api/typewriter/status` — what's currently being typed + cursor position
- `POST /api/typewriter/clear` — reset everything

each `GET /api/typewriter/current` returns `{"value": "00000000"}` (8 bits, from the txt panel truth table). panel poll rate = typing speed. 10 GETs/sec = 10 chars/sec.

### txt panel

- `GET /api/txtpanel` — all chars mapped to their 8-bit value
- `GET /api/txtpanel/table` — ordered list of `{value}` entries
- `GET /api/txtpanel/full` — raw 128-row truth table with shift/i5…i0/char/value
- `GET /api/txtpanel/current` — one value, changes every second
- `GET /api/txtpanel/hello` — cycles `Hello World! ` twice a second
- `GET /api/txtpanel/{char}` — value for a single character

### demo

- `GET /api/hello` — `{"message": "Hello from the API!"}`
- `GET /api/items/{id}` — path/query param demo
- `POST /api/items/` — json body demo

## how the typewriter works

1. someone types on the site and hits enter
2. site POSTs the text to `/api/typewriter`
3. panel GETs `/api/typewriter/current` repeatedly
4. every GET returns one char's 8-bit value and advances
5. after the text ends, 8 spaces are typed (pause), then it loops

the panel's poll rate controls how fast it types. the server has no timer — it just hands out the next char on demand.

## files

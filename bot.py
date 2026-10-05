import os, io, json, random, hashlib, datetime as dt, sys
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw, ImageFont

TZ = ZoneInfo("Europe/Paris")
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
MODE = os.environ.get("MODE", "test")          # test = ventes simulées
MIN_SALES, MAX_SALES = 40, 60
DAY_START, DAY_END = 0, 24                      # heures d'activité
AMOUNTS = [19, 24, 29, 30, 35, 39, 45, 49, 55, 59, 65, 79, 89, 99]
PSEUDOS = ["Kaïs_77","lunarix","xX_Maël_Xx","Zéphyr 🔥","naya.shop","Aleex_ツ","TomTom93","Sacha_fbr","ghostly ♡","yoann_ebay",
 "Mia ⚡","Rafael_09","nxtlvl","Dylan.p","Louis.m","Capucine🌸","enzo_off","Rémi_14","Zayn ✨","kylian.drop",
 "𝓜𝓪𝓷𝓸𝓼","Hugo_s","n0ah","Adam.bzh","Ilyes_ᴾᴿᴼ","swan_13","lenny-vnt","Maddie 🦋","ArthurLB","Jade.resell",
 "tiago_92","Océane_k","Noé.D","wassim_off","R0main","Lola ✦","baptiste.pro","Eliott_77","Yann_k","Nael_m",
 "Sofiane.v","clara_drop","Gabin 🔥","mathis__","Ambre.sells","lorenzo_x","Timéo_06","Kenzo_dls","alix.shop","OlivierB"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BRAND = {"etsy": ("Etsy", 0xF1641E), "ebay": ("eBay", 0x0064D2)}
STATE = "sent.json"
MAX_PER_RUN = 2                                 # jamais en paquet : 2 messages max par lancement

def plan_for(day):
    """Planning du jour, identique à chaque exécution (graine = date)."""
    r = random.Random(day.isoformat())
    total = r.randint(MIN_SALES, MAX_SALES)
    share_etsy = r.uniform(0.35, 0.45) if r.random() < 0.5 else r.uniform(0.55, 0.65)  # un côté domine
    sales, used = [], set()
    def new_amount():
        while True:
            euros = r.randint(15, 129)
            cents = r.choice([90, 99, 50, 80, 95]) if r.random() < 0.4 else r.randint(1, 99)
            a = round(euros + cents / 100, 2)
            if a not in used:
                used.add(a); return a
    cast = r.sample(PSEUDOS, r.randint(22, 32))
    buyers = [{"pseudo": p, "side": "etsy" if r.random() < share_etsy else "ebay",
               "w": r.choice([1, 1, 1, 2, 3])} for p in cast]
    for i in range(total):
        minute = r.randint(DAY_START * 60, DAY_END * 60 - 1)
        t = dt.datetime.combine(day, dt.time(minute // 60, minute % 60), TZ)
        b = r.choices(buyers, weights=[x["w"] for x in buyers])[0]
        sales.append({"id": f"{day}-{i}", "time": t, "side": b["side"],
                      "pseudo": b["pseudo"], "amount": new_amount()})
    return sorted(sales, key=lambda s: s["time"])

def image_name(p):
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFKD", p) if ord(c) < 0x250 and not unicodedata.combining(c))
    return n.strip() or "membre"

def make_image(side, amount, pseudo):
    pseudo = image_name(pseudo)
    from PIL import ImageFilter
    bg = Image.open(f"assets/bg_{side}.jpg").convert("RGBA")
    f = lambda s: ImageFont.truetype(FONT, s)
    # voile sombre à gauche pour la lisibilité
    veil = Image.new("RGBA", bg.size, (0, 0, 0, 0)); vd = ImageDraw.Draw(veil)
    for x in range(700):
        vd.line([(x, 0), (x, 720)], fill=(0, 0, 0, int(150 * (1 - x / 700))))
    bg.alpha_composite(veil)
    # logo
    logo = Image.open("assets/logo.png"); w = 340
    logo = logo.resize((w, int(logo.height * w / logo.width)), Image.LANCZOS)
    bg.alpha_composite(logo, (55, 45))
    d = ImageDraw.Draw(bg)
    lab, lpos, lf = "NOUVELLE VENTE D'UN MEMBRE", (58, 203), f(24)
    for blur, alpha in ((12, 255), (5, 200)):
        g = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text(lpos, lab, font=lf, fill=(255, 106, 19, alpha))
        bg.alpha_composite(g.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(bg).text(lpos, lab, font=lf, fill=(255, 140, 50, 255))
    # prix : lueur puis texte blanc net, sans contour
    txt = f"{amount:.2f}".replace(".", ",") + " €"
    pos, font = (55, 250), f(150)
    for blur, col, alpha in ((46, (255, 255, 255), 150), (22, (255, 255, 255), 230), (8, (255, 255, 255), 255)):
        g = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text(pos, txt, font=font, fill=col + (alpha,))
        bg.alpha_composite(g.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(bg).text(pos, txt, font=font, fill="white")
    # bandeau du bas : BRAVO @pseudo + badge plateforme
    bar = Image.new("RGBA", bg.size, (0, 0, 0, 0)); bd = ImageDraw.Draw(bar)
    bd.rounded_rectangle((55, 560, 640, 650), radius=18, fill=(0, 0, 0, 150), outline=(255, 255, 255, 40), width=1)
    bg.alpha_composite(bar)
    d = ImageDraw.Draw(bg)
    d.text((82, 585), "BRAVO", font=f(34), fill="white")
    d.text((222, 585), f"@{pseudo}", font=f(34), fill=(255, 140, 60, 255))
    name, color = BRAND[side]
    badge = {"etsy": (241, 100, 30), "ebay": (0, 100, 210)}[side]
    tw = d.textlength(name, font=f(24))
    d.rounded_rectangle((55, 500, 55 + tw + 40, 545), radius=22, fill=badge + (255,))
    d.text((75, 507), name, font=f(24), fill="white")
    buf = io.BytesIO(); bg.convert("RGB").save(buf, "PNG"); buf.seek(0)
    return buf

def send(s, now):
    name, color = BRAND[s["side"]]
    label = "[TEST] " if MODE == "test" else ""
    embed = {"title": f"🎉 {label}Nouvelle vente d'un membre Nova Club",
             "description": f"**{s['pseudo']}** vient de conclure une vente ! 🔥\n*{name}*",
             "color": color, "image": {"url": "attachment://vente.png"},
             "fields": [{"name": "📅 Date", "value": now.strftime("%Y-%m-%d")}],
             "footer": {"text": f"🚀 Toi aussi tu veux vendre comme ça ? Rejoins Nova Club • {now.strftime('%H:%M')}"}}
    img = make_image(s["side"], s["amount"], s["pseudo"])
    r = requests.post(WEBHOOK, data={"payload_json": json.dumps({"username": "Nova Ventes", "embeds": [embed]})},
                      files={"file": ("vente.png", img, "image/png")}, timeout=30)
    r.raise_for_status()

def main():
    now = dt.datetime.now(TZ)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    today = now.date().isoformat()
    state = {k: v for k, v in state.items() if k.startswith(today)}   # purge anciens jours
    sent_now = 0
    for s in plan_for(now.date()):
        if s["time"] <= now and s["id"] not in state:
            if (now - s["time"]).total_seconds() > 6 * 3600:   # trop vieux, on saute
                state[s["id"]] = "skipped"; continue
            if sent_now >= MAX_PER_RUN:
                break                                          # le reste partira au prochain lancement
            if sent_now:
                import time; time.sleep(random.uniform(8, 20))  # petite pause entre 2 messages
            send(s, dt.datetime.now(TZ)); state[s["id"]] = "sent"; sent_now += 1; print("envoyé", s["id"])
    json.dump(state, open(STATE, "w"))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":      # génère 2 images d'aperçu en local
        for side in ("etsy", "ebay"):
            open(f"preview_{side}.png", "wb").write(make_image(side, 52, "armen69").read())
    else:
        main()

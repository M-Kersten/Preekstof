# Toestemming vragen voor één dienst

Een uitgeschreven kerkdienst is niet van de app en niet van de maker ervan. Er staan namen in
en er staat in waarvoor gebeden is. Zonder dat iemand ja heeft gezegd hoort zo'n tekst hier
niet te staan, ook niet in een map die niet in git zit.

Wat hieronder staat is bedoeld om te mailen. Pas het aan zoals het bij jullie past, maar laat
er niets uit weg.

---

**Onderwerp:** Mogen we één dienst bewaren om de app mee te blijven testen?

Beste [naam],

Jullie gebruiken Preekstof nu een paar weken. Om de app beter te maken wil ik graag één
dienst van jullie bewaren als testdienst. Concreet gaat het om twee dingen:

- de uitgeschreven tekst van die dienst, zoals de app hem gemaakt heeft;
- welke fragmenten jullie er zelf uit gepost hebben.

Daar meet ik dan aan af of de app de goede momenten voorstelt. Zonder zulke diensten kan ik
alleen maar raden of een verandering hem beter of slechter maakt.

Wat er niet bij zit: de video, het geluid, en alles van andere diensten.

Waar het blijft staan: op mijn eigen computer, in een map die niet gedeeld wordt en niet op
internet staat. Het gaat niet naar Anthropic, niet naar Donkey Mobile, en niet naar iemand
anders. Als er ooit iets van gepubliceerd wordt, dan alleen als getal (bijvoorbeeld: "van de
vijf voorstellen werden er drie gepost"), nooit als tekst uit de preek.

Hoe lang: tot het einde van de pilot, of tot jullie zeggen dat het weg moet. Eén mailtje is
genoeg en dan is het weg, zonder dat ik vraag waarom.

Twee dingen om zelf te checken voordat je ja zegt:

1. Lees de uitgeschreven tekst van die dienst even door. Staat er een naam in van iemand die
   ziek is, of iets uit een gebed dat niet buiten de kerk hoort, kies dan een andere dienst.
   Ik kan dat niet voor jullie beoordelen.
2. Is de voorganger van die dienst iemand van buiten, laat het hem of haar dan even weten.

Mag het? Dan is "ja, dienst van [datum] mag" genoeg. Mag het niet, dan is dat ook prima en
verandert er niets aan jullie gebruik van de app.

Met vriendelijke groet,
[naam]

---

## Als het ja is

Kies de dienst en neem hem op in de meetset:

```bash
.venv/bin/python -m tools.adopt service-a1b2c3d4 --as 2026-03-08-kruispunt
```

Open daarna `evaluation/<naam>/service.json` en vul `church` en `permission` in. In
`permission` hoort te staan wie ja zei, wanneer, en waarvoor. Een lege regel daar betekent
dat niemand het meer weet, en dan is het antwoord over een half jaar nee.

Bewaar de mail zelf ook. Niet in dit mapje, gewoon in je mail.

## Als het nee wordt

Map weg en niets meer. Er zit niets van die kerk in de app zelf; `evaluation/` is de enige
plek waar een dienst van iemand anders kan blijven staan.

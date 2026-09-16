# Hoe de app de momenten kiest

Van opname tot een lijstje fragmenten waar je iets mee kunt. Dit beschrijft wat er
tussen die twee gebeurt, in de volgorde waarin het gebeurt.

## 1. Uitschrijven

De opname gaat door Whisper en komt eruit als zinnen met tijdcodes. Elke zin heeft een
begin en een eind in seconden. Die tijdcodes zijn later het enige waarop geknipt wordt,
dus alles wat daarna komt werkt met zinnen, nooit met losse woorden.

De woordenlijst van het merk gaat als hint mee naar Whisper: namen van voorgangers,
liedbundels, locaties. Wat je daarna in de ondertitels verbetert, onthoudt de app.

## 2. De dienst in stukken

`backend/structure.py` deelt de dienst in: welkom, zang, lezing, gebed, preek,
mededelingen, zegen. Dat gaat op stiltes, op lengte, op woorden die alleen in een
bepaald deel vallen, en op waar in de dienst je zit. Zang herken je aan de gaten tussen
de zinnen, mededelingen aan de agenda-taal.

Ongeveer de helft van een dienst is geen preek. Die helft gaat niet naar het model. Dat
scheelt geld, en het scheelt een lijst met momenten waar niemand iets aan heeft.

## 3. De preek in één stuk

Wat overblijft gaat in zo min mogelijk stukken weg. Veertig minuten past in één vraag,
en daar blijft bijna elke preek onder. Alleen een dienst die daaroverheen gaat wordt
gesplitst, en die stukken vertrekken dan tegelijk.

Zo ging het niet altijd. Vensters van vier minuten, een minuut overlap, twee minuten
aanloop per venster. Een dienst van anderhalf uur werd zestien vragen, drie tegelijk, en
daarna nog een ronde om de antwoorden met elkaar te vergelijken. Drie keer wachten
voordat er iets op het scherm stond. Wie snel één clip wil hebben scrubt in die tijd zelf
door de preek.

Een preek is ongeveer twintigduizend tokens. Dat past ruim binnen wat een model in één
keer kan lezen. Elke zin gaat nu één keer de deur uit in plaats van soms twee keer, en de
vaste instructie gaat één keer mee in plaats van zestien keer.

Splitst een preek toch, dan krijgt het tweede stuk een minuut van wat eraan voorafging,
apart gemarkeerd: lezen mag, kiezen niet. Zonder die aanloop kan een model niet zien of
een fragment op zichzelf staat. "Dat is precies wat God bedoelt" leest prima als je de
vorige twee minuten kent, en is niets als je ze niet kent.

Het model hoort ook waar het zit: welk deel van de dienst, hoeveel minuten na het begin,
hoe de dienst is opgebouwd, en wat de kerk zelf heeft ingevuld over de preek.

## 4. Eén ronde: voorstellen en kiezen tegelijk

Eén vraag, met de hele preek erin. Het model mag drie tot zes momenten voorstellen, het
sterkste eerst, en dat zijn meteen de momenten die gepost worden. Wie alles gelezen heeft
weet welk moment het beste van de dienst is; daar hoeft niemand achteraf meer overheen.

De opdracht draait om één kijker: iemand die scrolt, blijft hangen en twee seconden heeft
om te snappen waar dit over gaat. Fragmenten die openen op "dat", "die", "daarom", "dus"
of "zoals ik net zei" vallen af, hoe mooi de zin verderop ook is.

Wat terugkomt wordt vastgezet op zinsgrenzen, en fragmenten korter dan 25 of langer dan
180 seconden gaan eruit. Wat overblijft krijgt een score: 45 tot 90 seconden telt op,
onder de 30 of boven de 120 telt af, en een fragment dat opent op een terugverwijzing
telt af.

Het antwoord wordt bewaard onder een naam die alles bevat wat het model te horen kreeg,
plus het model zelf. Loopt een run vast, dan wordt alleen de rest opnieuw gevraagd.
Verandert er iets aan de tekst of de instructie, dan is de cache ongeldig en wordt er
niets ouds teruggegeven.

## 4b. Zelf knippen, terwijl het zoeken loopt

De uitgeschreven tekst staat op het scherm zodra hij klaar is. Dus ook voordat het zoeken
begint, en de hele tijd dat het loopt. Wie om twaalf uur een clip af moet hebben heeft
niets aan een balkje dat vult, en weet meestal al half welk moment hij hebben wil.

Onder **Hele tekst** staat de dienst zin voor zin met tijdcodes. Typen in het zoekveld
markeert elke treffer en loopt er met ‹ › doorheen; accenten en hoofdletters tellen niet
mee, dus "mattheus" vindt "Mattheüs". De delen van de dienst staan als knopjes bovenaan,
met de minuut waarop ze beginnen, want een ochtend heeft drie blokken zang en aan het
woord alleen zie je niet welke. Klik op een zin en de opname speelt daar verder. Tijdens
het afspelen wordt de zin die gezegd wordt gemarkeerd en schuift de lijst mee, tot je zelf
scrollt.

Shift-klikken op een tweede zin pakt alles ertussen. Onderaan staat wat dat aan tijd is,
of dat te kort of te lang is voor een reel, en de openingswoorden als naam. **Fragment
maken** zet het in dezelfde lijst waar het zoeken in schrijft.

Die twee kunnen elkaar niet in de weg zitten. Wat je zelf knipt draagt een merkteken dat
het zoeken nooit aanraakt:

- Een ronde die terugkomt leest de dienst eerst van schijf. Een fragment dat je knipte
  terwijl het model nadacht staat er daarna nog.
- Opslaan mag terwijl het zoeken loopt, en de server voegt samen in plaats van overschrijft:
  een moment dat de browser nog niet gezien heeft komt erbij. Weggooien doet de browser
  alleen bij zijn eigen fragmenten, en die kent hij per definitie.
- Ze staan boven de gevonden momenten. Een rangorde waar ze nooit in meededen hoort ze niet
  naar beneden te duwen.
- **Opnieuw zoeken** vervangt wat het zoeken vond en laat ze staan.

Alleen **Gekozen fragmenten verwerken** zet de lijst echt op slot, want dat loopt de
fragmenten stuk voor stuk af. Tijdens het zoeken zegt de balk onderaan dat hij nog even
wacht.

## 5. Overlap opruimen

Twee voorstellen die hetzelfde moment zien blijven niet allebei staan. Overlappen ze voor
meer dan de helft, dan blijft de hoogst scorende staan en worden de andere grenzen
eronder bewaard als alternatief. Die kun je in het scherm nog kiezen.

## 6. Tweede ronde: alleen bij een preek die niet in één stuk paste

Past de preek er wel in, dan slaat de app deze ronde over en scheelt dat een minuut
wachten. Anders komt hij terug, want dan zag het model per stuk maar een deel van de
dienst en gaf het per stuk een confidence. Die getallen zijn onderling niets waard: het
beste moment van een saai stuk krijgt net zo makkelijk een 0,9 als het beste moment van
de dienst.

Die ronde krijgt alles tegelijk: de opbouw van de dienst, elk voorstel met titel,
samenvatting, reden, de openingszin apart, een waarschuwing als die openingszin
terugverwijst, en een stuk transcript. Daaruit kiest hij er drie tot zes, op volgorde,
met per voorstel één zin waarom het het wel of niet werd.

Afvallers worden niet weggegooid. Ze staan onder "Ook gevonden, niet gekozen", met de
reden erbij. Ben je het er niet mee eens, dan pak je ze alsnog.

## Waarom het er zo weinig zijn

Een dienst van een uur levert makkelijk vijftien bruikbare passages op. Daarvan kan een
kerk er wekelijks twee of drie echt afmaken. Een lijst van twaalf is dan geen rijkdom
maar werk: je moet ze allemaal beluisteren om te ontdekken dat er drie goed zijn.

En langer is beter dan korter. Een fragment van 25 seconden dat begint bij de rake zin
laat de kijker achter in een verhaal dat hij niet kent. Hetzelfde moment met veertig
seconden aanloop erbij vertelt zichzelf. Dat is de reden dat de ondergrens omhoog is
gegaan en de voorkeur bij 45 tot 90 seconden ligt.

## Waar je zelf aan kunt draaien

- **Merk → woorden van deze kerk**: namen die de computer niet kan raden. Hoe beter die
  lijst, hoe minder je in de ondertitels hoeft te verbeteren, en hoe beter het model
  leest wat er staat.
- **Waar gaat de preek over**: titel en serie op de dienstpagina. Gaan mee naar beide
  rondes en helpen vooral bij het herkennen van de rode draad.
- **Nauwkeurig uitschrijven**: trager, hoort meer. Loont bij slecht geluid.
- **Opnieuw zoeken**: de bewaarde antwoorden blijven staan zolang tekst en instructie
  gelijk blijven, dus een tweede run kost bijna niets zolang er alleen stukken overgedaan
  hoeven worden.
- **`LLM_PASSAGE_MINUTES` in config.env**: hoeveel dienst er in één vraag gaat. Staat op
  40. Zet hem op 4 en je hebt de oude vensters terug, inclusief de acht minuten wachten.
- **`LLM_EFFORT` in config.env**: hoe lang het model nadenkt voordat het antwoordt. Staat
  op medium. Met nog één vraag over is dit vrijwel de hele wachttijd, dus hier zit de
  knop tussen sneller en scherper.

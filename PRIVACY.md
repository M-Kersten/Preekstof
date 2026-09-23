# Wat er met jullie opname gebeurt

Eén pagina, bedoeld om aan een kerkenraad te geven. Wie liever de korte versie leest: die
staat in de app zelf, bij het scherm waar de kosten van het zoeken staan.

Versie 0.10.0 (pilot). Als de app op iets anders draait dan wat hier staat, klopt deze pagina
niet meer; het versienummer staat onderin het gereedheidspaneel.

## In het kort

De opname en het geluid blijven op jullie eigen computer. Van de preek gaat de uitgeschreven
tekst naar Anthropic, het bedrijf achter Claude, om de goede stukken te vinden. Verder gaat er
niets weg. Naar de maker van deze app gaat helemaal niets: er zit geen telemetrie in en er is
geen server waar de app mee praat.

## Wat waar blijft

**Op jullie computer, en nergens anders.** De video van de dienst. Het geluid. De hele
uitgeschreven tekst van de dienst. De clips die eruit komen. De woordenlijst die de app van
jullie leert. De instellingen. De logbestanden.

**Naar Anthropic (api.anthropic.com).** De uitgeschreven tekst van het preekgedeelte, in één
aanvraag per dienst, met jullie eigen API-sleutel. En per fragment dat je klaarzet nog één
kleine aanvraag: de ondertitels van dat fragment, om verkeerd verstane woorden eruit te halen.
Dat is dus ook tekst uit de preek, van de stukken die jullie zelf gekozen hebben. Er gaat nooit beeld of geluid heen.
Onder de zakelijke voorwaarden van de API wordt wat je stuurt niet gebruikt om modellen te
trainen. Anthropic bewaart aanvragen tijdelijk voor misbruikcontrole; wat daarvoor geldt staat
in hun eigen voorwaarden, die tussen jullie kerk en Anthropic gelden en niet via deze app
lopen. Als je erbij zet waar de preek over gaat, gaat dat mee. Sinds versie 0.10.0 gaat de naam
van de voorganger ook mee, als naam en verder niets, omdat het model die naam dan beter
verstaat in de tekst.

**Naar Kerkdienstgemist.** Alleen als jullie het stationnummer invullen: de app vraagt de
lijst met jullie eigen openbare diensten op en haalt de opname op achter dezelfde
downloadknop die op jullie eigen pagina staat. Dat is precies wat de browser van een bezoeker
ook doet. Het beeldje bij elke dienst komt van dezelfde plek.

**Naar Hugging Face.** Eenmalig, bij het eerste gebruik: het spraakmodel en het model dat
personen herkent. Alleen downloaden, er gaat niets heen.

**Naar de maker van deze app.** Niets. Geen gebruikscijfers, geen foutmeldingen, geen
versiecontrole met een kenmerk erin. Als er iets misgaat, maakt de app een bestand dat jullie
zelf kunnen lezen en zelf kunnen mailen. Zie *Als er iets misgaat* hieronder.

## Het stuk waar het echt om gaat

Een uitgeschreven kerkdienst is geen gewone tekst. Er staan namen van zieke gemeenteleden in.
Er staat in waarvoor gebeden is, en soms waarom. Er staan dingen in die mensen in vertrouwen
aan de kerk hebben verteld en niet aan een Amerikaans bedrijf.

Onder de AVG zijn gegevens over gezondheid en over geloof bijzondere persoonsgegevens, en
voor die twee gelden strengere regels dan voor een naam en een adres. Een gebed voor iemand
die net een diagnose heeft gekregen valt daaronder. Een dienst waarin iemand belijdenis doet
valt daaronder.

De app stuurt alleen het preekgedeelte, omdat hij de dienst in stukken knipt en het
voorbedengedeelte overslaat. Dat scheelt, maar het is een inschatting van een computer en
geen garantie. Een voorganger die tijdens de preek een naam noemt, stuurt die naam mee.

Wil je dat laatste niet, zet dan `POLISH_CLIPS=0` in `config.env`. Dan gaat alleen de preek
nog naar Claude om momenten te zoeken, en blijven de ondertitels zoals ze verstaan zijn.

**Wil de kerk dit helemaal niet, dan hoeft het niet.** Zet in `config.env`:

    LLM_PROVIDER=ollama

Dan draait het zoeken naar momenten op een model op jullie eigen computer en gaat er geen
letter de deur uit. Uitschrijven en knippen gebeurde al op de computer zelf. De app werkt dan
volledig binnen het gebouw. Het kost wel een computer die zwaar genoeg is, en de gevonden
momenten zijn minder goed dan met Claude.

## Hoe lang blijft het staan

Opnames en werkbestanden blijven staan tot iemand ze weggooit. In `config.env` staat:

    KEEP_WEEKS=4

Bij het starten ruimt de app alles op wat ouder is dan dat aantal weken. Zet je er `0`, dan
ruimt hij niets automatisch op.

Met de hand: **Ruimte vrijmaken**, boven in de balk. Daar staat per dienst hoeveel er ligt, en
je gooit een dienst of alleen de opname eruit. De uitgeschreven tekst en de gemaakte clips
kun je apart houden, omdat daar het werk in zit.

Alles weg wil zeggen: de mappen `services/`, `projects/` en `logs/` weggooien. Daar staat
alles in wat over een dienst gaat. De map `templates/` bevat jullie merk en jullie
instellingen, en geen diensten.

## Als er iets misgaat

Naast elke foutmelding staat **Melding opslaan**. Dat maakt één zip-bestand: de versie, deze
computer, wat er misging, de laatste vierhonderd regels van het logboek, de instellingen, en
de staat van de dienst waar het misging. De uitgeschreven tekst zit er niet bij. De
API-sleutel is eruit gehaald.

Dat bestand gaat nergens heen. Het komt bij jullie downloads te staan. Jullie kunnen het
openen en lezen voordat jullie besluiten het te mailen, en als jullie het niet mailen gebeurt
er niets mee.

## Wie ziet de API-sleutel

De sleutel staat in `config.env` op jullie eigen computer, in gewone tekst, zoals een
wachtwoord in een instellingenbestand. Wie bij die computer kan, kan hem lezen. Hij staat niet
in het logboek en niet in een melding; op allebei die plekken wordt hij eruit gefilterd.

De rekening van Claude komt bij degene op wiens naam de sleutel staat. Reken op ongeveer drie
cent per dienst.

## Wat de app niet doet

Geen account, geen inloggen, geen server. De app draait op één computer en luistert alleen
naar die computer zelf. Andere computers in het gebouw kunnen er niet bij, ook niet als ze op
hetzelfde netwerk zitten.

Er is geen analytics, geen crashrapportage, geen "help ons de app te verbeteren". Wat er in
het gebouw gebeurt blijft in het gebouw, behalve de uitgeschreven preek en alleen als jullie
Claude gebruiken.

## Vragen

Voor de voorwaarden van Anthropic: hun eigen commerciële voorwaarden en privacybeleid, die
gelden tussen de kerk en Anthropic. Voor de voorwaarden van Kerkdienstgemist: die van
Kerkdienstgemist zelf; deze app vraagt daar niets extra's.

Voor de app zelf staat in `NOTICE` op wiens werk hij gebouwd is en onder welke voorwaarden.

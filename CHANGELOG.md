# Wat er verandert

Per versie, in gewone taal. Welke versie jij draait staat onderin het paneel dat opengaat
als je in de balk op **Alles gereed** klikt.

## 0.11.0 — pilot

Een gemaakte video is nog geen geplaatste video. Deze versie gaat over de stap daartussen.

**Na Video maken opent Klaar om te delen.** Daar staat de clip, en ernaast wat je ermee kunt.
Het venster komt later terug onder **Delen en downloaden**, op de plek waar eerst alleen een
downloadlink stond.

**Dezelfde clip in drie vormen.** Staand 9:16 voor Reels, Shorts, TikTok en een WhatsApp-status.
Tijdlijn 4:5 voor Facebook en de tijdlijn van Instagram, waar een staande video wordt afgekapt.
Vierkant voor Facebook op de computer, de website en de nieuwsbrief. Het is steeds dezelfde clip:
de ondertitels, het beeldkader, het volgen van de spreker, het logo en de muziek gaan mee. In de
bredere vormen komt er meer van de kerk naast de spreker in beeld, en de ondertitels staan lager,
omdat er in een tijdlijn niets over de video heen ligt. De afsluiter wordt voor elke vorm opnieuw
getekend, met logo en regels in het midden. Een vorm die nog niet gemaakt is, laat meteen zien hoe
het beeld erin valt. Maken is één klik, en met **Voortaan altijd meemaken** gebeurt het daarna bij
elke clip vanzelf.

Wie na het maken nog een woord verbetert, ziet bij de vormen van daarvoor staan dat ze van vóór
die wijziging zijn.

**De tekst onder de post staat klaar.** Claude schrijft er drie: een korte voor Instagram, een
met iets meer context voor Facebook en een zin of twee om door te sturen via WhatsApp. Het
schrijft alleen de tekst zelf. Wat eronder hoort zet de app erbij, uit wat jullie één keer
instellen: de link naar de hele dienst met jullie vaste hashtags, en het bijbelgedeelte als de clip
er een noemt. Een link die een taalmodel zelf opschrijft kan verkeerd zijn, en een verkeerde link
onder een post van de kerk is erger dan geen link.

Wat Claude schrijft wordt nagelopen. Een citaat moet woord voor woord in de clip staan. Een
bijbeltekst moet in de clip genoemd zijn, of in wat jullie over de dienst invulden, en een
hoofdstuk of vers dat niemand uitsprak valt weg. Kopiëren is één knop. Wat je zelf aanpast blijft
staan.

Of een post je of u zegt, kies je in het venster zelf. Daar staan ook de vaste hashtags en de
link naar de diensten, en later vind je ze terug onder **Merk instellen → Delen**. Kost ongeveer een
tiende cent per clip. Zonder sleutel, of met `WRITE_POSTS=0` in config.env, maakt de app een
eenvoudige tekst uit de titel van de clip.

**Onder de motorkap.** Het eindscherm werd vlak voor het maken van een video al die tijd niet
bijgewerkt; dat gebeurde alleen bij het opstarten en bij het opslaan van het merk. Dat klopt nu.
Windows weigert een video te vervangen die nog openstaat in een speler. De app wacht daar nu even
op, in plaats van een render van een minuut weg te gooien.

## 0.10.0 — pilot

Alles wat er sinds de eerste pilotversie bij kwam: de app draait nu ook op een computer
waar niemand iets op hoeft te installeren, hij zegt wat hij doet terwijl hij het doet, en
hij weigert werk waar de schijf te klein voor is.

**Je ziet welke dienst je kiest.** De lijst van Kerkdienstgemist stond vol met vier keer
"Morgendienst" onder elkaar. Nu staat er een beeldje uit de opname naast, en wie er
voorging als je kerk dat invult op je eigen pagina. Dat beeldje loopt mee naar binnen: het
blijft bij de dienst staan in de app, ook nadat de opname is opgeruimd. Wie voorging gaat
ook mee naar Claude, als naam en verder niets, dus namen worden beter verstaan.

**De ondertitels worden nog een keer nagelezen.** Een spraakmodel hoort klanken en schrijft
"de brief aan de eveneers", omdat het niet weet dat daar maar één woord kan staan. Nadat een
fragment netjes is uitgeschreven leest Claude de ondertitels één keer na, met de hele
woordenlijst erbij en zonder ruimtegrens. Hij mag alleen een woord vervangen door een woord
dat al op de lijst staat, evenveel woorden terug als hij weghaalt, en verder niets: geen
grammatica, geen zinnen mooier maken. Wat er staat moet zijn wat er gezegd is.

Wat hij twee keer op dezelfde manier verbetert, komt in de woordenlijst van jullie kerk te
staan. Daarna wordt het gewoon vervangen en hoeft er niets meer gevraagd te worden. Kost
ongeveer een tiende cent per fragment. Uit te zetten met `POLISH_CLIPS=0` in config.env.

**Meer kerkwoorden bereiken het spraakmodel.** Van de zeventig woorden in de woordenlijst
kwamen er dertig helemaal niet aan, waaronder alle bijbelboeken: Whisper leest maar een stukje
van zo'n lijst en de rest valt eraf zonder dat iemand dat merkt. Er blijkt een tweede plek te
zijn die net zo groot is, en die was ongebruikt. Alles wat niet paste gaat daar nu heen. Op een
voorgelezen testzin kwamen er zo 11 van de 12 kerkwoorden terug in plaats van 7, en op een
tweede zin 4 van de 8 in plaats van nul. In
`woordenlijst.json` staat nu ook een lijst `hotwords` waar je zelf woorden bij kunt zetten.

Op een Mac met mlx-whisper bestaat die tweede plek niet, dus daar verandert er niets.

**Eén keer klikken op Windows.** Had je nog geen Python, dan installeerde start.bat hem en
vroeg daarna om het venster te sluiten en opnieuw te beginnen. Dat hoeft niet meer: hij zoekt
zelf op waar Python terechtkwam en gaat door. En start.bat praat nu Nederlands.

**Geen klus die halverwege de schijf volmaakt.** De app rekent vooraf uit wat uitschrijven
of clips maken aan ruimte kost en weigert als het niet past, met hoeveel het nodig heeft,
hoeveel er vrij is en hoeveel er onder Ruimte vrijmaken klaarstaat. Raakt de schijf vol
terwijl een opname binnenkomt, dan stopt dat ophalen op tijd.

**"Op" en "even vol" zijn twee verschillende dingen.** Een Claude-account zonder tegoed gaf
dezelfde melding als een account dat even aan zijn limiet zat, en de app wachtte er net zo
lang op. Nu zegt hij meteen dat er tegoed op moet en waar je dat doet.

**Eén dienst tegelijk.** Twee tabbladen konden twee diensten tegelijk laten draaien op een
computer die er één aankan. Nu wacht de tweede, met de reden erbij.

**Niet meer stilstaan zonder iets te zeggen.** De eerste keer uitschrijven haalt een
spraakmodel van 460 MB op. Tot nu toe zei de balk "Het spraakmodel wordt geladen" en stond
hij op vier procent, hoe lang het ook duurde. Nu staat er hoeveel megabyte binnen is, van
hoeveel, en dat het één keer gebeurt.

**Doe de proef.** Onderin het gereedheidspaneel staat een knop die tien seconden gesproken
tekst door de hele molen haalt: geluid eruit, uitschrijven, beelden nakijken, een clip maken.
Je ziet per stap of het werkte en hoe lang het duurde, en de clip komt eronder te staan. Gaat
er iets mis, dan weet je dat binnen een minuut in plaats van twintig minuten nadat je een
dienst van anderhalf uur hebt ingezet. Wat eruit komt gaat mee in een melding.

**Als het misgaat, heb je iets om te sturen.** Alles wat het zwarte venster zegt komt nu ook
in `logs/preekstof.log` te staan, met de vier vorige keren ernaast. Naast elke foutmelding, en
onderin het gereedheidspaneel, staat **Melding opslaan**: dat zet één bestand bij je downloads
met wat er misging, deze computer, de laatste regels van het logboek en je instellingen. De
sleutel is eruit gehaald. Er gaat niets automatisch ergens heen; jij mailt het, of je mailt het
niet.

**Een download in plaats van een clone.** Bij Releases op GitHub staat nu een zip die alles
bevat wat de app nodig heeft. Uitpakken, start.bat of start.command aanklikken, klaar. Bij het
starten kijkt de app één keer of er een nieuwere is en zegt dat in het zwarte venster, met wat
er verandert en waar je hem haalt. Bijwerken doe je zelf, wanneer het jou uitkomt.

**Op papier wat er naar buiten gaat.** `PRIVACY.md` staat erbij: één pagina voor een
kerkenraad, over wat er op de computer blijft, wat er naar Claude gaat, en wat er in een
uitgeschreven preek kan staan waar je niet aan denkt. De korte versie staat in de app, bij de
kosten.

## 0.9.0 — pilot

De eerste versie die bedoeld is om bij een andere kerk te draaien dan die van de maker.

**Welkomstscherm.** Open je de app voor het eerst, dan legt hij eerst uit wat hij doet en
vraagt daarna de drie dingen die hij nodig heeft: een sleutel voor Claude, de naam van de
kerk, en het nummer van jullie pagina op Kerkdienstgemist. De sleutel wordt meteen
uitgeprobeerd, dus een verkeerd geplakte sleutel zegt dat op het scherm en niet pas twintig
minuten later. Kerkdienstgemist kun je overslaan als jullie er niet op staan; dan opent de
app vanzelf op het tabblad om een bestand te kiezen. Alles wat je hier invult blijft
aanpasbaar onder **Merk instellen**, en via **Instellen opnieuw** loop je de stappen nog een
keer langs.

**Geen Kladblok meer nodig.** De sleutel hoeft niet meer met de hand in config.env. Hij
wordt geschreven én meteen in gebruik genomen, dus de app hoeft er niet voor herstart.

**Een versienummer.** Staat onderin het gereedheidspaneel. Bij een melding is dat het eerste
wat gevraagd wordt.

**Een gat dicht.** Zolang de app draaide kon elke website die je open had staan de
uitgeschreven tekst van een dienst van deze computer lezen en diensten weggooien. Alleen de
app zelf mag er nu nog bij.

**Niet meer andermans kerk.** Een nieuwe installatie heette "Nieuwe Kerk Utrecht", omdat die
naam meekwam in de bestanden. Nu staat er niets tot jij het invult.

**Een licentie.** LICENSE en NOTICE staan erbij: wat je met deze app mag, en op wiens werk
hij gebouwd is.

## Daarvoor

Geen losse versies. De app werd bij één kerk gebouwd en gebruikt, en wat er veranderde staat
in de commits en in `docs/ROADMAP.md`.

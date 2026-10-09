# Wat er verandert

Per versie, in gewone taal. Welke versie jij draait staat onderin het paneel dat opengaat
als je in de balk op **Alles gereed** klikt.

## 0.12.0 — pilot

Uitschrijven werkt weer op de Mac. Wie 0.11.0 op een Mac installeerde, kreeg bij elke dienst een
foutmelding over `metadata_errors` voordat er een woord gehoord was.

De download voor de Mac haalt bij de eerste start een onderdeel voor het geluid op, en kreeg de
nieuwste versie. Die kende een instelling niet meer die het spraakmodel meegeeft. De app leest het
geluid nu zelf in, dus dat onderdeel doet bij het uitschrijven niet meer mee, en het blijft
bovendien op een versie die werkt. Bijwerken gaat vanuit de app: klik in de balk op **nieuwe
versie** en dan op **Bijwerken**.

Voordat een versie online komt, schrijft elke download op een echte Windows-computer en op twee
echte Macs nu ook een zin uit. Daar zat deze fout, en daar werd niet naar gekeken.

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

**Muziek kies je op het gehoor.** Elke track staat in een lijst met een afspeelknop ernaast.
Die speelt de eerste vijftien seconden, want daar begint de muziek ook onder je clip, en komt
zacht op en gaat zacht weg. Er speelt er steeds één tegelijk, en naast de naam staat hoe lang de
track duurt.

Er komt nu ook een standaardbibliotheek mee met de app: muziek die elke kerk meteen kan
gebruiken, onder **Standaard** in de lijst. Eigen muziek uploaden kan daarnaast, en staat onder
**Eigen muziek**. Een eigen nummer gooi je weg met het kruisje; de standaardnummers blijven staan.

**Ondertitels en logo stel je één keer in.** Wie vijf clips uit een dienst haalde, moest bij elke
clip opnieuw de letter, de kleur en het logo kiezen. Clips uit een dienst kregen de stijl van het
merk niet eens mee. Wat je nu in één clip verandert, gaat mee naar de andere clips die nog niet
gemaakt zijn, en elke nieuwe clip begint ermee. Een clip die al een video heeft blijft zoals hij
is. Moet één clip er anders uitzien, vink dan **Alleen voor deze clip** aan.

**Begin en einde bijstellen gaat op het gehoor.** Onder **Begin en einde bijstellen** staan de
woorden rond de knip, met een gouden streep op de plek waar hij nu valt. Klik op een woord en de
clip begint of eindigt daar, met een ademhaling ruimte zodat het woord niet wordt afgekapt. Met
**‹ zin** en **zin ›** spring je naar het vorige of volgende zinseinde. Na elke verandering hoor
je meteen de laatste drie seconden tot de knip, of de eerste drie erna, en de speler stopt precies
waar de clip ophoudt. Valt de knip midden in een woord, dan staat dat erbij.

**De clips van een dienst staan overzichtelijk onderin.** De balk onderaan liet de klaarstaande
clips zien als een rij titels waar je zijwaarts doorheen moest scrollen, en een fragment dat je
twee keer verwerkte stond er twee keer in, met dezelfde titel. Nu staat er hoeveel fragmenten
klaar zijn, en **Bekijken** opent een lijst met één regel per fragment, in de volgorde van de
dienst. Is een fragment vaker verwerkt, dan staan de versies onder de titel, de nieuwste bovenaan,
met begin en einde erbij. Twee versies met precies hetzelfde begin en einde staan zo gemarkeerd. Een
oude versie gooi je daar weg met **Weghalen**. Bij het fragment zelf staat nu ook dat het verwerkt
is, met een knop naar de clip, en wie het nog een keer kiest leest wat er dan gebeurt.

**Scherper beeld bij het uitsnijden.** Een staande video uit een brede opname is altijd een
vergroting. Uit een opname van 1280×720, zoals Kerkdienstgemist die vaak levert, wordt elke pixel
2,7 pixels in de clip, nog voor er ingezoomd wordt. De app rekte dat beeld op de eenvoudigste
manier op. Nu gebruikt hij een nauwkeurigere methode, haalt hij eerst wat compressieruis weg en
verscherpt hij daarna een beetje, meer naarmate het beeld verder vergroot is. Op een echte opname
van 1 Mbit/s zijn haar, ogen en stof duidelijk scherper. Het maken duurt ongeveer 7% langer.

Automatisch inzoomen op een kleine spreker gaat minder ver: tot 2,7 keer vergroot in plaats van
3,2. Uit een 720p-opname wordt dan niet meer ingezoomd, uit 1080p tot ongeveer anderhalf keer.
Onder de zoomschuif staat hoe groot de opname is en hoe ver hij vergroot wordt. Wordt het zichtbaar
zacht, dan staat dat er in rood bij.

**Kleur en contrast worden verbeterd.** Veel opnames uit de kerk zijn vlak: er zit geen echt zwart
en geen echt wit in, en weinig kleur. De app meet nu per clip op twaalf beeldjes hoe donker en hoe
licht het beeld echt gaat, rekt dat op tot het volle bereik en geeft een flets beeld tot een vijfde
meer kleur. Een opname die het bereik al gebruikt blijft zoals hij is, en er is een grens zodat het
nooit overdreven wordt. De witbalans blijft van de camera: een gekleurd kleed of beamerlicht stuurt
een automatische witbalans de verkeerde kant op. De schakelaar staat onder **Beeldkader**, staat
voor nieuwe clips aan en geldt, net als de ondertitelstijl, voor al je clips die nog niet gemaakt
zijn. Het voorbeeld doet de correctie na; helemaal gelijk aan de video is dat niet. Clips die al
een video hebben blijven zoals ze gemaakt zijn.

Een AI-upscaler is ook geprobeerd. Die maakt randen strakker, maar gezichten worden wasachtig, en
op een gewone computer kost hij vier seconden per beeldje: een uur voor een clip van een halve
minuut. Die zit er dus niet in.

**De spreker volgen gaat rustiger.** Het kader zette in één keer op volle snelheid aan en stond
net zo abrupt weer stil, vaak met de spreker nog aan de rand, zodat de volgende beweging een
moment later al begon. Nu trekt het kader langzaam op, haalt de spreker terug naar het midden en
komt zacht tot stilstand. Wie rustig over het podium loopt, wordt in één doorgaande beweging
gevolgd. Een enkele keer dat het gezicht verkeerd gezien wordt, verschuift het kader niet meer.
Dit geldt voor clips die je vanaf nu maakt.

**Het eindscherm ziet eruit zoals in het instellingenvenster.** Drie dingen weken af. De tekst
stond in de video veel kleiner dan in het voorbeeld; in Poppins bijna de helft. Het kleurverloop
kreeg bij elke keer opnieuw maken een andere richting. En met een camerabeweging zoomden tekst en
logo mee, waardoor het leek alsof alles anders in beeld stond. Nu beweegt alleen de achtergrond,
en dat zie je ook in het voorbeeld. Tekst en logo blijven staan waar je ze neerzet.

Hetzelfde verschil in lettergrootte zat in het voorbeeld van de ondertitels. De video zelf
verandert daar niet, het voorbeeld wel: dat laat de ondertitels nu even groot zien als ze in de
video komen.

**Alle diensten van Kerkdienstgemist in de lijst.** De lijst met diensten van je kerk liet alleen
de tien nieuwste zien. Kerkdienstgemist geeft ze per tien, en onderaan staat nu **Oudere diensten
laden**, met hoeveel er in totaal staan. Zo kom je tot de oudste dienst die Kerkdienstgemist nog
bewaart. Bij Nieuwe Kerk Utrecht zijn dat er nu 26, terug tot april.

**Geen vastgelopen scherm meer na bijwerken zonder herstart.** Werk je de app bij terwijl het
zwarte venster openstaat, dan draait de server nog de oude code terwijl het scherm al nieuw is. De
balk die daarvoor waarschuwt keek alleen naar het versienummer, en dat verandert pas bij een nieuwe
release. Daardoor liep het bewerken van een clip vast op een melding over `on`. Nu vergelijken
scherm en server ook een vingerafdruk van de code, dus de balk verschijnt meteen, en de editor
loopt niet meer vast op een veld dat de oude server niet meestuurt.

**Een download per computer, met alles erin.** Voor Windows, voor een Mac met Apple-chip en
voor een Mac met Intel-processor is er nu een eigen download. Python en alle onderdelen zitten
erin, dus uitpakken en dubbelklikken is genoeg: geen Python installeren, geen tweede keer starten.
Een paar dingen mag de download van hun licentie niet meebrengen. FFmpeg en één onderdeel voor
het geluid haalt Preekstof bij de eerste start op, zoals het dat met FFmpeg altijd al deed. De
installatiepagina zegt per computer welke knop het is en waar je klikt als Windows of de Mac
waarschuwt dat ze de app nog niet kennen.

Elke download is voordat hij online gaat uitgepakt en gestart op een echte Windows-computer en op
twee echte Macs, via start.bat en start.command, tot en met een proefclip met ondertitel. Daarbij
kwamen twee fouten boven die elke Mac geraakt zouden hebben. De server met FFmpeg voor de Mac
weigerde de app. En na uitpakken met een dubbelklik was start.command geen programma meer maar
een tekstbestand. Allebei opgelost.

**Je eigen werk staat in een eigen map.** Diensten, clips, het merk, logo's, muziek, het
eindscherm, de woordenlijst en de sleutel staan voortaan in de map `Preekstof` in je
persoonlijke map, los van de app. De app zelf kan zo in zijn geheel vervangen worden zonder dat
er iets van jullie verdwijnt. Bij de eerste start van deze versie verhuist de app wat er in de
oude map stond, één keer, zonder iets te overschrijven, en zegt in het zwarte venster waar het
staat. Niet in Documenten: die map wordt op veel laptops door OneDrive of iCloud bijgehouden, en
een opname van een dienst is twee gigabyte.

**Bijwerken vanuit de app.** Is er een nieuwe versie, dan staat er in de balk **nieuwe versie**.
In het paneel daaronder staat in één regel wat er verandert, met een knop **Bijwerken**. Die
haalt de download voor deze computer op en controleert hem. Daarna start **Nu opnieuw starten**
de app opnieuw met de nieuwe versie, en het scherm laadt vanzelf opnieuw zodra die draait. Er
gebeurt niets zonder dat iemand op de knop drukt.

**Een rustiger eerste start.** Het zwarte venster spreekt Nederlands en toont bij het installeren
één regel die meeloopt, in plaats van bladzijden Engels. Wat er precies gebeurde staat in een
logbestand, en komt alleen op het scherm als het misgaat. Het spraakmodel, zo'n 460 MB, komt
binnen terwijl je de app verkent, en het paneel rechtsboven laat zien hoe ver het is. Bij de
eerste dienst hoef je er dan niet meer op te wachten.

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

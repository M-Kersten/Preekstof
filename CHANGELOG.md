# Wat er verandert

Per versie, in gewone taal. Welke versie jij draait staat onderin het paneel dat opengaat
als je in de balk op **Alles gereed** klikt.

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

**Je ziet welke dienst je kiest.** De lijst van Kerkdienstgemist stond vol met vier keer
"Morgendienst" onder elkaar. Nu staat er een beeldje uit de opname naast, en wie er
voorging als je kerk dat invult op je eigen pagina. Dat beeldje loopt mee naar binnen: het
blijft bij de dienst staan in de app, ook nadat de opname is opgeruimd. Wie voorging gaat
ook mee naar Claude, als naam en verder niets, dus namen worden beter verstaan.

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

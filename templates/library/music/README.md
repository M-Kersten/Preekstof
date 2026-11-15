# Standaardbibliotheek muziek

De nummers hier zijn van Scott Buckley (https://www.scottbuckley.com.au/library/), uitgebracht
onder CC BY 4.0. Wie er een gebruikt, moet in de beschrijving van de post deze regel zetten:

    'Titel' by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au

Die regel staat per nummer in `tracks.json` als `attribution`. De app laat hem zien in het
muziekpaneel en zet hem zelf onder elke posttekst van een clip met dat nummer. Hij vraagt ook
om de muziek niet los te verspreiden of op muziekdiensten te zetten; ze hoort onder video.

Wat in deze map staat, komt mee met elke kopie en elke release van de app. Kerken zien het
in de muzieklijst onder **Standaard**, boven hun eigen muziek. Hun eigen uploads staan in
`templates/music/`, die git niet bijhoudt, zodat een update die nooit raakt.

## Een nummer toevoegen

1. Zet het bestand hier neer: mp3, m4a, wav, aac of ogg. Een mp3 van 128 tot 192 kbps is
   genoeg onder gesproken woord en houdt de download klein.
2. Zet het in `tracks.json`, met een titel en de maker:

   ```json
   { "file": "rustige-piano.mp3", "title": "Rustige piano", "credit": "Naam van de maker (CC BY 4.0)",
     "attribution": "De regel die de licentie onder elke post wil" }
   ```

   `attribution` mag weg als de licentie geen vaste regel in de beschrijving vraagt.

3. Commit en push. Het staat in de volgende release.

Gebruik alleen muziek die je mag meeleveren én die kerken mogen gebruiken op Instagram,
Facebook en YouTube. Vraagt de licentie om naamsvermelding, zet die dan bij `credit`: de app
laat hem zien naast het nummer.

Een kerk kan een nummer uit deze map niet weggooien, en een eigen upload mag niet dezelfde
bestandsnaam hebben als een nummer hier.

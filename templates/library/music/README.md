# Standaardbibliotheek muziek

Wat in deze map staat, komt mee met elke kopie en elke release van de app. Kerken zien het
in de muzieklijst onder **Standaard**, boven hun eigen muziek. Hun eigen uploads staan in
`templates/music/`, die git niet bijhoudt, zodat een update die nooit raakt.

## Een nummer toevoegen

1. Zet het bestand hier neer: mp3, m4a, wav, aac of ogg. Een mp3 van 128 tot 192 kbps is
   genoeg onder gesproken woord en houdt de download klein.
2. Zet het in `tracks.json`, met een titel en de maker:

   ```json
   { "file": "rustige-piano.mp3", "title": "Rustige piano", "credit": "Naam van de maker (CC BY 4.0)" }
   ```

3. Commit en push. Het staat in de volgende release.

Gebruik alleen muziek die je mag meeleveren én die kerken mogen gebruiken op Instagram,
Facebook en YouTube. Vraagt de licentie om naamsvermelding, zet die dan bij `credit`: de app
laat hem zien naast het nummer.

Een kerk kan een nummer uit deze map niet weggooien, en een eigen upload mag niet dezelfde
bestandsnaam hebben als een nummer hier.

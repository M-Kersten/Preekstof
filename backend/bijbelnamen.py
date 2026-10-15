"""Names from the Bible, in the spellings Dutch churches use, for polish to reach for.

Whisper writes "Simpson" where a preacher said Simson: it knows the cartoon better than the
judge. The reading pass knows Simson the moment it sees him next to Gideon, but it may
only bring in a name somebody wrote down, and nobody writes down every name in the Bible.
This is that list, written down once.

It is not sent with the question. The model knows these names already; this is only what
the answer is checked against, so the length costs nothing. Whisper's own hints stay
short (transcription.initial_prompt): measured on ten minutes of a real sermon, the odd
names came back with and without any hints, and dropping the names from the hints made
"Paulus" into "powders".

Several spellings where churches differ: NBG, NBV and HSV do not agree on Jacob, Matteüs
or Betlehem, and a fix that is right in one church is not wrong in the next.
"""

PEOPLE = """
Adam Eva Kaïn Abel Set Henoch Methusalem Noach Sem Cham Jafet Nimrod Abram Abraham Sara Saraï
Hagar Ismaël Isaak Rebekka Ezau Esau Jakob Jacob Laban Lea Rachel Ruben Simeon Levi Juda Dan
Naftali Gad Aser Issakar Zebulon Jozef Benjamin Dina Tamar Potifar Efraïm Manasse Lot
Melchisedek Mozes Aäron Mirjam Jetro Sippora Zippora Farao Jozua Kaleb Bileam Rachab Achan
Debora Barak Gideon Jefta Simson Delila Ruth Naomi Noömi Orpa Boaz Obed Isaï Elkana Hanna
Peninna Eli Samuel Saul Jonathan Michal David Goliath Abigaïl Batseba Uria Natan Nathan
Absalom Joab Abner Salomo Rehabeam Jerobeam Achab Izebel Elia Elisa Naäman Hizkia Josia
Jesaja Jeremia Ezechiël Daniël Hosea Joël Amos Obadja Jona Micha Nahum Habakuk Sefanja
Zefanja Haggai Zacharia Maleachi Ezra Nehemia Ester Esther Mordechai Haman Job
Nebukadnessar Belsazar Darius Kores Cyrus Sadrach Mesach Abednego
Jezus Christus Messias Immanuël Maria Jozef Johannes Elisabet Elizabeth Zacharias Anna
Petrus Simon Kefas Andreas Jakobus Filippus Bartolomeüs Bartholomeüs Thomas Tomas Mattheüs
Matteüs Matthijs Thaddeüs Judas Iskariot Matthias Paulus Saulus Barnabas Silas Timoteüs
Timotheüs Titus Lucas Lukas Marcus Markus Stefanus Ananias Saffira Cornelius Lydia
Priscilla Aquila Apollos Filemon Onesimus Martha Marta Lazarus Nicodemus Zacheüs Bartimeüs
Jaïrus Pilatus Herodes Kajafas Annas Barabbas Magdalena Gabriël Michaël Satan Beëlzebul
"""

PLACES = """
Eden Ur Haran Kanaän Israël Egypte Gosen Sinaï Horeb Moria Karmel Sion Zion Jeruzalem
Jerusalem Bethlehem Betlehem Nazaret Nazareth Galilea Judea Samaria Kapernaüm Kafarnaüm
Betanië Bethanië Emmaüs Jericho Jordaan Golgotha Golgota Getsemane Gethsémané Babel Babylon
Ninevé Nineve Assyrië Edom Moab Ammon Filistea Gaza Hebron Bethel Betel Silo Sodom Gomorra
Tyrus Sidon Kana Bethsaïda Betsaïda Gadara Dekapolis Siloam Bethesda Damascus Tarsus
Antiochië Efeze Korinte Korinthe Filippi Thessalonica Tessalonica Athene Rome Galatië
Kolosse Patmos Macedonië Cyprus Kreta Malta Laodicea Smyrna Pergamum Sardis Filadelfia
"""

NAMES = tuple(dict.fromkeys((PEOPLE + PLACES).split()))

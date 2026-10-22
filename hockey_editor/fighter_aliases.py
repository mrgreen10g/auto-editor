"""English identity / Uzbek Latin spelling pairs, not rankings or fight records.

English names are cross-checked against fighter_roster.UFC_NAMES. Uzbek spellings
are editorial transliterations and accepted input variants, not official UFC
translations. Keep full names; do not map a surname to a unique person.
"""
VERSION='ufc-uz-2026-10-22'
# English | preferred Uzbek | additional full-name input variants
_ROWS="""
Lone'er Kavanagh|Loner Kavana|Leron Kavana;Loneer Kavanagh;Loneer Kavana;Loner Kavanag
Ramazan Temirov|Ramazon Temirov
Petr Yan|Petr Yan|Pyotr Yan
Merab Dvalishvili|Merab Dvalishvili
Islam Makhachev|Islom Maxachev|Islam Maxachev;Islom Makhachev
Khabib Nurmagomedov|Habib Nurmagomedov|Xabib Nurmagomedov
Umar Nurmagomedov|Umar Nurmagomedov
Said Nurmagomedov|Said Nurmagomedov
Abubakar Nurmagomedov|Abubakar Nurmagomedov
Conor McGregor|Konor Makgregor|Konor MakGregor
Jon Jones|Jon Jons
Tom Aspinall|Tom Aspinall
Ciryl Gane|Siril Gan|Siryl Gan
Alexander Volkov|Aleksandr Volkov
Sergei Pavlovich|Sergey Pavlovich
Curtis Blaydes|Kertis Bleyds
Waldo Cortes Acosta|Valdo Kortes Akosta|Waldo Cortes-Acosta
Serghei Spivac|Sergey Spivak
Marcin Tybura|Marchin Tibura
Derrick Lewis|Derrik Lyuis
Tai Tuivasa|Tay Tuivasa
Jailton Almeida|Jailton Almeyda|Jeylton Almeyda
Tallison Teixeira|Tallison Teysheyra
Ante Delija|Ante Deliya
Rizvan Kuniev|Rizvan Kuniyev
Josh Hokit|Josh Hokit
Valter Walker|Valter Uoker
Shamil Gaziev|Shamil Gaziyev
Alex Pereira|Aleks Pereyra|Aleks Pereira
Magomed Ankalaev|Magomed Ankalayev
Jiří Procházka|Irji Proxazka|Jiri Prochazka;Yirji Proxazka
Carlos Ulberg|Karlos Ulberg
Jan Błachowicz|Yan Blaxovich|Jan Blachowicz
Jamahal Hill|Jamal Hill
Khalil Rountree Jr.|Xalil Rauntri|Khalil Rountree;Xalil Rauntri Junior
Nikita Krylov|Nikita Krilov
Aleksandar Rakić|Aleksandar Rakich|Aleksandar Rakic
Volkan Oezdemir|Volkan Ozdemir
Dominick Reyes|Dominik Reyes
Johnny Walker|Jonni Uoker
Azamat Murzakanov|Azamat Murzakanov
Bogdan Guskov|Bogdan Guskov
Anthony Smith|Entoni Smit
Alonzo Menifield|Alonzo Menifild
Modestas Bukauskas|Modestas Bukauskas
Oumar Sy|Umar Si
Khamzat Chimaev|Hamzat Chimayev|Xamzat Chimayev;Hamzat Chimaev
Dricus Du Plessis|Drikus Dyu Plessi|Drikus Du Plessi
Sean Strickland|Shon Striklend
Israel Adesanya|Israel Adesanya|Izrael Adesanya
Nassourdine Imavov|Nassurdin Imavov
Robert Whittaker|Robert Uittaker|Robert Vittaker
Caio Borralho|Kayo Borralyo
Anthony Hernandez|Entoni Ernandes
Reinier de Ridder|Reyner de Ridder
Jared Cannonier|Jared Kannonir
Paulo Costa|Paulo Kosta
Roman Dolidze|Roman Dolidze
Marvin Vettori|Marvin Vettori
Brendan Allen|Brendan Allen
Michael Venom Page|Maykl Peyj|Maykl Pej;Michael Page
Shara Magomedov|Shara Magomedov|Sharabutdin Magomedov
Joe Pyfer|Jo Payfer
Gregory Rodrigues|Gregori Rodriges
Jack Hermansson|Jek Hermansson
Michel Pereira|Mishel Pereyra
Ikram Aliskerov|Ikrom Aliskerov
Nursulton Ruziboev|Nursulton Ro'ziboyev|Nursulton Ruziboyev;Nursulton Roziboyev
Makhmud Muradov|Mahmud Murodov|Mahmud Muradov
Jack Della Maddalena|Jek Della Maddalena
Shavkat Rakhmonov|Shavkat Rahmonov|Shavkat Raxmonov
Kamaru Usman|Kamaru Usmon
Belal Muhammad|Belal Muhammad
Leon Edwards|Leon Edvards
Ian Machado Garry|Ien Machado Gerri|Ian Garry;Ien Gerri
Sean Brady|Shon Bredi
Joaquin Buckley|Xoakin Bakli
Carlos Prates|Karlos Prates
Gilbert Burns|Gilbert Berns
Geoff Neal|Jeff Nil
Colby Covington|Kolbi Kovington
Stephen Thompson|Stiven Tompson
Vicente Luque|Visente Luke
Michael Morales|Maykl Morales
Gabriel Bonfim|Gabriel Bonfim
Daniel Rodriguez|Daniel Rodriges
Mike Malott|Mayk Malott
Yaroslav Amosov|Yaroslav Amosov
Rinat Fakhretdinov|Rinat Faxretdinov
Muslim Salikhov|Muslim Salihov
Justin Gaethje|Jastin Getji|Justin Getji
Ilia Topuria|Iliya Topuriya|Ilia Topuriya
Arman Tsarukyan|Arman Sarukyan|Arman Tsarukian
Charles Oliveira|Charlz Oliveyra|Charlz Oliveira
Max Holloway|Maks Hollouey|Maks Xollouey
Dustin Poirier|Dastin Porye|Dastin Puarye
Dan Hooker|Den Huker
Mateusz Gamrot|Mateush Gamrot
Beneil Dariush|Beneil Dariush
Rafael Fiziev|Rafael Fiziyev
Renato Moicano|Renato Moykano
Benoît Saint Denis|Benua Sen Deni|Benoit Saint Denis
Paddy Pimblett|Peddi Pimblett
Michael Chandler|Maykl Chendler
Mauricio Ruffy|Maurisio Ruffi
Grant Dawson|Grant Douson
Jalin Turner|Jeylin Terner
Joel Álvarez|Xoel Alvares|Joel Alvarez
Alexander Volkanovski|Aleksandr Volkanovski
Movsar Evloev|Movsar Yevloyev|Movsar Evloyev
Diego Lopes|Diego Lopes
Yair Rodriguez|Yair Rodriges
Brian Ortega|Brayan Ortega
Arnold Allen|Arnold Allen
Aljamain Sterling|Aljameyn Sterling
Josh Emmett|Josh Emmett
Lerone Murphy|Leron Merfi
Jean Silva|Jan Silva
Giga Chikadze|Giga Chikadze
Bryce Mitchell|Brays Mitchell
Dan Ige|Den Ige
Youssef Zalal|Yusuf Zalal
Joanderson Brito|Joanderson Brito
Pat Sabatini|Pet Sabatini
Aaron Pico|Aaron Piko
Kevin Vallejos|Kevin Valyexos
Sean O'Malley|Shon O'Melli|Shon Omelli;Sean OMalley
Cory Sandhagen|Kori Sendhagen
Song Yadong|Song Yadong
Deiveson Figueiredo|Deyvison Figeyredu
Marlon Vera|Marlon Vera
Rob Font|Rob Font
Mario Bautista|Mario Bautista
Aiemann Zahabi|Ayman Zahabi
Henry Cejudo|Genri Sexudo|Henri Sejudo
Kyler Phillips|Kayler Fillips
Dominick Cruz|Dominik Kruz
Payton Talbott|Peyton Talbott
Vinicius Oliveira|Vinisius Oliveyra|Vinisius Oliveira;Vinisius Oliveyra
Marcus McGhee|Markus Makgi
Farid Basharat|Farid Basharat
Javid Basharat|Javid Basharat
Montel Jackson|Montel Jekson
Joshua Van|Joshua Van
Alexandre Pantoja|Aleksandre Pantoja
Brandon Royval|Brendon Royval
Brandon Moreno|Brendon Moreno
Amir Albazi|Amir Albazi
Kai Kara-France|Kay Kara Frans|Kai Kara France
Tatsuro Taira|Tatsuro Tayra
Asu Almabayev|Asu Almabayev
Alex Perez|Aleks Peres
Manel Kape|Manel Kape
Steve Erceg|Stiv Erseg
Tim Elliott|Tim Elliott
Tagir Ulanbekov|Tagir Ulanbekov
Charles Johnson|Charlz Jonson
Bruno Silva|Bruno Silva
Sumudaerji|Sumudaerji
Rei Tsuruya|Rey Tsuruya
Zhang Weili|Chjan Veyli|Zhang Veyli
Mackenzie Dern|Makkenzi Dern
Virna Jandiroba|Virna Jandiroba
Tatiana Suarez|Tatyana Suares
Yan Xiaonan|Yan Syaonan
Amanda Lemos|Amanda Lemos
Jessica Andrade|Jessika Andrade|Jéssica Andrade
Amanda Ribas|Amanda Ribas
Marina Rodriguez|Marina Rodriges
Iasmin Lucindo|Yasmin Lusindo
Loopy Godinez|Lupi Godines
Tabatha Ricci|Tabata Richchi
Gillian Robertson|Jillian Robertson
Karolina Kowalkiewicz|Karolina Kovalkyevich
Angela Hill|Anjela Hill
Tecia Pennington|Tesiya Pennington
Fatima Kline|Fatima Klayn
Denise Gomes|Deniz Gomes
Valentina Shevchenko|Valentina Shevchenko
Manon Fiorot|Manon Fioro
Alexa Grasso|Aleksa Grasso
Erin Blanchfield|Erin Blanchfild
Maycee Barber|Meysi Barber
Natalia Silva|Nataliya Silva
Rose Namajunas|Rouz Namayunas
Katlyn Cerminara|Ketlin Serminara
Jessica Eye|Jessika Ay
Tracy Cortez|Treysi Kortes
Jasmine Jasudavicius|Jasmin Jasudavichus
Karine Silva|Karine Silva
Viviane Araújo|Vivian Araujo|Viviane Araujo
Ariane da Silva|Ariane da Silva
Miranda Maverick|Miranda Maverik
Wang Cong|Van Tsun
Casey O'Neill|Keysi O'Nil|Keysi Onil
Kayla Harrison|Keyla Harrison
Julianna Peña|Julianna Penya|Julianna Pena
Raquel Pennington|Rakel Pennington
Ketlen Vieira|Ketlen Viyeyra
Norma Dumont|Norma Dyumon
Irene Aldana|Iren Aldana
Macy Chiasson|Meysi Chiasson
Mayra Bueno Silva|Mayra Bueno Silva
Yana Santos|Yana Santos
Miesha Tate|Misha Teyt
Holly Holm|Holli Holm
Pannie Kianzad|Panni Kianzad
Karol Rosa|Karol Roza
Ailin Perez|Aylin Peres
Jacqueline Cavalcanti|Jaklin Kavalkanti
Nora Cornolle|Nora Kornoll
Joselyne Edwards|Joselin Edvards
Amanda Nunes|Amanda Nunes
Ronda Rousey|Ronda Rouzi
José Aldo|Joze Aldo|Jose Aldo
Georges St-Pierre|Jorj Sen Pyer|Georges St Pierre
Anderson Silva|Anderson Silva
Stipe Miocic|Stipe Miochich
Francis Ngannou|Frensis Ngannu
Tony Ferguson|Toni Fergyuson
Nate Diaz|Neyt Dias
Nick Diaz|Nik Dias
Zarrukh Adashev|Zarruh Adashev|Zarrux Adashev
Kyoji Horiguchi|Kyoji Horiguchi|Kyoji Xoriguchi
David Martinez|David Martines
Raul Rosas Jr.|Raul Rosas|Raul Rosas Junior
Raoni Barcelos|Raoni Barselos
Steve Garcia|Stiv Garsiya
Melquizael Costa|Melkizael Kosta
Patricio Pitbull|Patrisio Pitbul|Patrisio Freyre;Patricio Freire
David Onama|David Onama
Quillan Salkilld|Kuillan Salkild
Salahdine Parnasse|Salohiddin Parnas|Saladin Parnas
Tom Nolan|Tom Nolan
Uroš Medić|Urosh Medich|Uros Medic
Neil Magny|Nil Magni
Christian Leroy Duncan|Kristian Leroy Dankan
Abus Magomedov|Abus Magomedov
Bo Nickal|Bo Nikal
Navajo Stirling|Navajo Stirling
Muhammad Saidov|Muhammad Saidov
Vitor Petrino|Vitor Petrino
Tyrell Fortune|Tayrell Forchun
Mario Pinto|Mario Pinto
Alexia Thainara|Aleksiya Taynara
Mizuki|Mizuki|Mizuki Inoue
Eduarda Moura|Eduarda Moura
Gabriella Fernandes|Gabriella Fernandes
Regina Tarin|Regina Tarin
Luana Santos|Luana Santos
Bia Mesquita|Bia Meskita
Michelle Montague|Mishel Montegyu
Chelsea Chandler|Chelsi Chendler
Alice Pereira|Alis Pereyra
Mitch Raposo|Mitch Raposo
Imanol Rodriguez|Imanol Rodriges
Pavel Andrusca|Pavel Andrushka
Jamall Emmers|Jamal Emmers
Tofiq Musayev|Tofik Musayev
Esteban Ribovics|Esteban Ribovich
Kevin Holland|Kevin Holland
Roman Kopylov|Roman Kopilov
Edmen Shahbazyan|Edmen Shaxbazyan
Abdul Rakhman Yakhyaev|Abdulrahmon Yahyayev|Abdul Raxman Yaxyayev
Brando Peričić|Brando Perichich|Brando Pericic
Anthony Wint|Entoni Vint
Piera Rodriguez|Piera Rodriges
Talita Alencar|Talita Alenkar
Sam Hughes|Sem Hyuz
Carli Judice|Karli Judis
Melissa Croden|Melissa Krouden
"""
FIGHTER_NAMES=tuple(tuple([p[0],p[1],tuple(p[2].split(';')) if len(p)>2 else ()])
                    for row in _ROWS.strip().splitlines() if (p:=row.split('|')))

# Both ranking tables served by https://www.ufc.com/rankings on 2026-10-22.
# Identity coverage only: no numeric rankings, records, outcomes or odds.
RANKED_SNAPSHOT = ('Islam Makhachev', 'Alexander Volkanovski', 'Justin Gaethje', 'Petr Yan', 'Ilia Topuria', 'Joshua Van', 'Sean Strickland', 'Tom Aspinall', 'Merab Dvalishvili', 'Alex Pereira', 'Ciryl Gane', 'Khamzat Chimaev', 'Arman Tsarukyan', 'Alexandre Pantoja', 'Carlos Ulberg', 'Manel Kape', 'Brandon Royval', 'Tatsuro Taira', 'Kyoji Horiguchi', 'Lone’er Kavanagh', 'Asu Almabayev', 'Brandon Moreno', 'Amir Albazi', 'Ramazan Temirov', 'Tim Elliott', 'Steve Erceg', 'Sumudaerji', 'Tagir Ulanbekov', 'Alex Perez', "Sean O'Malley", 'Song Yadong', 'Umar Nurmagomedov', 'Mario Bautista', 'Cory Sandhagen', 'Payton Talbott', 'David Martinez', 'Aiemann Zahabi', 'Raul Rosas Jr.', 'Marlon Vera', 'Deiveson Figueiredo', 'Marcus McGhee', 'Raoni Barcelos', 'Bryce Mitchell', 'Movsar Evloev', 'Diego Lopes', 'Lerone Murphy', 'Aljamain Sterling', 'Jean Silva', 'Yair Rodriguez', 'Arnold Allen', 'Youssef Zalal', 'Kevin Vallejos', 'Steve Garcia', 'Aaron Pico', 'Melquizael Costa', 'Brian Ortega', 'Patricio Pitbull', 'David Onama', 'Charles Oliveira', 'Max Holloway', 'Paddy Pimblett', 'Benoît Saint Denis', 'Quillan Salkilld', 'Mauricio Ruffy', 'Salahdine Parnasse', 'Mateusz Gamrot', 'Rafael Fiziev', 'Renato Moicano', 'Dan Hooker', 'Tom Nolan', 'Beneil Dariush', 'Ian Machado Garry', 'Carlos Prates', 'Michael Morales', 'Jack Della Maddalena', 'Gabriel Bonfim', 'Sean Brady', 'Belal Muhammad', 'Leon Edwards', 'Kamaru Usman', 'Mike Malott', 'Yaroslav Amosov', 'Uroš Medić', 'Joaquin Buckley', 'Daniel Rodriguez', 'Neil Magny', 'Dricus Du Plessis', 'Nassourdine Imavov', 'Brendan Allen', 'Caio Borralho', 'Joe Pyfer', 'Gregory Rodrigues', 'Anthony Hernandez', 'Israel Adesanya', 'Christian Leroy Duncan', 'Jared Cannonier', 'Abus Magomedov', 'Ikram Aliskerov', 'Bo Nickal', 'Shara Magomedov', 'Magomed Ankalaev', 'Jiří Procházka', 'Khalil Rountree Jr.', 'Navajo Stirling', 'Paulo Costa', 'Azamat Murzakanov', 'Dominick Reyes', 'Jan Błachowicz', 'Bogdan Guskov', 'Robert Whittaker', 'Alonzo Menifield', 'Muhammad Saidov', 'Reinier de Ridder', 'Nikita Krylov', 'Alexander Volkov', 'Sergei Pavlovich', 'Josh Hokit', 'Curtis Blaydes', 'Waldo Cortes Acosta', 'Rizvan Kuniev', 'Vitor Petrino', 'Serghei Spivac', 'Ante Delija', 'Valter Walker', 'Derrick Lewis', 'Tyrell Fortune', 'Aleksandar Rakić', 'Mario Pinto', 'Valentina Shevchenko', 'Kayla Harrison', 'Zhang Weili', 'Natalia Silva', 'Mackenzie Dern', 'Alexa Grasso', 'Manon Fiorot', 'Tatiana Suarez', 'Erin Blanchfield', 'Julianna Peña', 'Virna Jandiroba', 'Jasmine Jasudavicius', 'Rose Namajunas', 'Raquel Pennington', 'Denise Gomes', 'Gillian Robertson', 'Yan Xiaonan', 'Fatima Kline', 'Loopy Godinez', 'Alexia Thainara', 'Jéssica Andrade', 'Tabatha Ricci', 'Amanda Lemos', 'Amanda Ribas', 'Angela Hill', 'Mizuki', 'Maycee Barber', 'Wang Cong', 'Tracy Cortez', 'Miranda Maverick', 'Karine Silva', "Casey O'Neill", 'Eduarda Moura', 'Gabriella Fernandes', 'Regina Tarin', 'Joselyne Edwards', 'Ailin Perez', 'Norma Dumont', 'Yana Santos', 'Luana Santos', 'Jacqueline Cavalcanti', 'Macy Chiasson', 'Karol Rosa', 'Bia Mesquita', 'Michelle Montague', 'Nora Cornolle', 'Chelsea Chandler', 'Alice Pereira', 'Mitch Raposo', 'Imanol Rodriguez', 'Rei Tsuruya', 'Charles Johnson', 'Montel Jackson', 'Pat Sabatini', 'Pavel Andrusca', 'Joanderson Brito', 'Jamall Emmers', 'Tofiq Musayev', 'Grant Dawson', 'Esteban Ribovics', 'Kevin Holland', 'Roman Kopylov', 'Edmen Shahbazyan', 'Modestas Bukauskas', 'Abdul Rakhman Yakhyaev', 'Johnny Walker', 'Brando Peričić', 'Anthony Wint', 'Piera Rodriguez', 'Talita Alencar', 'Sam Hughes', 'Carli Judice', 'Melissa Croden')

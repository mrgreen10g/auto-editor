"""Seed name vocabulary, NOT a complete or automatically current squad database.
Names only; no ages, results, injuries, or club affiliations.
Sources checked 2026-09-29:
https://www.uefa.com/european-qualifiers/teams/47--germany/squad/
https://www.uefa.com/european-qualifiers/teams/147--serbia/squad/
https://www.uefa.com/european-qualifiers/teams/35--denmark/squad/
https://www.uefa.com/european-qualifiers/teams/110--portugal/squad/
https://www.uefa.com/european-qualifiers/teams/144--wales/squad/
https://www.uefa.com/european-qualifiers/teams/101/squad/
"""
import re,unicodedata
NAMES='''Oliver Baumann;Alexander Nübel;Antonio Rüdiger;Jonathan Tah;Nico Schlotterbeck;Joshua Kimmich;Leon Goretzka;Florian Wirtz;Leroy Sané;Serge Gnabry;Nick Woltemade;Karim Adeyemi
Predrag Rajković;Djordje Petrović;Strahinja Pavlović;Nikola Milenković;Nemanja Maksimović;Saša Lukić;Filip Kostić;Lazar Samardžić;Luka Jović;Aleksandar Mitrović;Dušan Vlahović;Andrija Živković
Kasper Schmeichel;Mads Hermansen;Joachim Andersen;Andreas Christensen;Joakim Mæhle;Christian Eriksen;Christian Nørgaard;Morten Hjulmand;Pierre-Emile Højbjerg;Rasmus Højlund;Mikkel Damsgaard;Kasper Dolberg
Diogo Costa;Rúben Dias;Diogo Dalot;Nuno Mendes;João Cancelo;Bruno Fernandes;Bernardo Silva;João Neves;Cristiano Ronaldo;Gonçalo Ramos;João Félix;Rafael Leão
Karl Darlow;Danny Ward;Chris Mepham;Neco Williams;Ben Davies;Joe Rodon;Ethan Ampadu;David Brooks;Harry Wilson;Aaron Ramsey;Brennan Johnson;Daniel James
Ørjan Nyland;Leo Østigård;Julian Ryerson;Kristoffer Ajer;Patrick Berg;Sander Berge;Martin Ødegaard;Antonio Nusa;Oscar Bobb;Alexander Sørloth;Erling Haaland;Jørgen Strand Larsen'''
PLAYERS=tuple(v.strip() for v in NAMES.replace('\n',';').split(';') if v.strip())

def plain(text):
    text=text.casefold().translate(str.maketrans({'ø':'o','æ':'ae','đ':'d'}))
    return ''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))

def mentioned_names(text):
    t=plain(text)
    return [name for name in PLAYERS if re.search(r'(?<!\w)'+re.escape(plain(name.split()[-1]))+r"(?:ning|ni|ga|da|dan)?(?!\w)",t)]

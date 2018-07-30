import logging, sys, os, requests, re
from collections import Counter
from math import exp, log10
from itertools import islice
import networkx as nx
import xml.etree.ElementTree as ET
from github import Github
logging.basicConfig(format='%(asctime)s | %(levelname)s : %(message)s', level=logging.INFO, stream=sys.stdout)
from itertools import islice
#import matplotlib.pyplot as plt
#from heapdict import heapdict
import random
#import numpy as np, scipy.stats as st
from .data import lang_codes, rename, remove
from tqdm import tqdm
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# CLASSES

class Word:
    """ Word object. One node in result graph. One word item containing
    information (lemma, language, tags)"""
    def __init__(self, lemma, lang, s=[]):
        """
        :param lemma (str): lemma
        :param lang (str): language
        :param s (list): list of tags
        """
        if lemma == None: self.lemma = ''
        else: self.lemma = lemma
        self.lang = lang
        self.s = s
        
    def __str__(self):
        """
        :return: string representation of Word object
        :rtype: str
        """
        if self.s:
            if isinstance(self.s[0],list):
                w = '['+'_'.join(['-'.join(i) for i in self.s])+']'
            else: w = '['+'-'.join(self.s)+']'
        else: w = '-'
        return str(self.lang)+'$'+str(self.lemma)+'$'+str(w)
    
    __repr__ = __str__
    
    def __eq__(self, other):
        """
        Equality : language and lemma absolute match + tags match one
        of variants.
        
        :rtype: boolean
        """
        return self.lemma == other.lemma and self.lang == other.lang and (self.s == other.s or other.s in self.s or self.s in other.s)
    
    def __lt__(self, other):
        """
        Less than (self, other) : if self is equal and other has more
        variants in tags.
        
        :rtype: boolean
        """
        if self.lang == other.lang and self.lemma == other.lemma:
            s1 = set(self.s)
            s2 = set(other.s)
            if (not s1 - s2) and (s1&s2==s1) and (s2 - s1): return True
            else: return False
        else: return False
    
    def __hash__(self): return hash(str(self))
    
    def write(self, mode='mono'):
        """
        Write method: 
        
        1. mode='mono' : lemma + tag variants (language is specified in
        filename) - for preprocessed monolingual dictionary
        2. mode='bi' : language, lemma, tags - for preprocessed 
        bilingual dictionary
        3. mode='out': lemma + tag (1) - for preview and further
        converting into section for insertion in dictionary. If there are
        several tag variants the first one (most popular) will be chosen.
        
        :param mode (str): mode of writing
        :return: string representation of Word object for storing in file
        :rtype: str
        """
        if mode == 'mono': return self.lemma + '\t' + '$'.join([str(i) for i in self.s])
        elif mode == 'bi': return self.lang + '\t' +  self.lemma + '\t' + '$'.join([str(i) for i in self.s])
        elif mode == 'out' and len(self.s)<1: return self.lemma + '\t'+''
        elif mode == 'out'and len(self.s)>=1: return self.lemma + '\t' + str(self.s[0])

class Tags(list):
    """One set of tags (e.g. n+m+sg)"""
    
    def __le__(self, other):
        """
        Less or equal : the second is not smaller than the first one,
        intersection = first.
        
        :rtype: boolean
        """
        s1 = set(self)
        s2 = set(other)
        if not s1 - s2 and s1&s2==s1: return True
        else: return False
    
    def __lt__(self, other):
        """
        Less than : the second is larger + intersection = first.
        
        :rtype: boolean
        """
        s1 = set(self)
        s2 = set(other)
        if (not s1 - s2) and (s1&s2==s1) and (s2 - s1): return True
        else: return False
    
    def __eq__(self, other):
        """
        Equal : perfect match
        
        :rtype: boolean
        """
        if set(self) == set(other): return True
        else: return False
        
    def __str__(self): return '-'.join(self)
    
    __repr__ = __str__
    
    def __hash__(self): return hash(str(self))

class WordDict(dict):
    """
    One word dictionary with tag variants (used for sorting them and
    combining words into multivariant tags object)
    
    It has the only attribute lemma that contains lemma and a method
    with the same name that sets this attribute.
    """
    def lemma(self, lemma): self.lemma = lemma

class FilteredDict(dict):
    """
    Dictionary for counting how many variants of tag occur. Filter by
    lemma. Key: lemma, value: dictionary with tag combination keys and
    number of entries with this combination.
    
    Methods:
    - set_lang : save language name
    - lemma : set lemma
    - add : add entry
    """
    def set_lang(self, lang): self.lang = lang
    
    def lemma(self, lemma): return self[self.lang+'_'+lemma]
        
    def add(self, word):
        lemma = word.lang+'_'+word.lemma
        tags = Tags(word.s)
        if lemma in self:
            if tags in self[lemma]: self[lemma][tags] += 1
            else: self[lemma][tags] = 1
        else:
            self[lemma] = WordDict()
            self[lemma].lemma(lemma)
            self[lemma][tags] = 1

class DiGetItem:
    """
    Word is a complex structure. Equality of objects doesn't mean that
    hash is the same (example in Word class). So we can't use hash to
    find whether we already have this word or not. Search in non-hash
    structures like list is inefficient.
    
    Dictionary : words with one tag variant. Hash can be used to get a
    word. It returns the same word.
    
    List : word with multiple variants. List search (check all one by
    one until we find the match). Returns full word (with all tags)
    
    Methods:
    
    - add : adds word
    - __getitem__ : return word (full or the same)
    - __len__ : len(dict) + len(list)
    """
    def __init__(self):
        self.list = []
        self.dict = {}
    
    def add(self, word):
        if len (word.s) > 1: self.list.append(word)
        else: self.dict[word] = word
    
    def __getitem__(self, key):
        key2 = Word(key.lemma, key.lang, [''])
        if key in self.dict: return self.dict[key]
        else:
            if key2 in self.dict: return self.dict[key2]
            try:
                key = self.list[self.list.index(key)]
                return key
            except:
                pass
    def __len__(self):
        return len(self.list)+len(self.dict)

class SetWithFilter(set):
    """Methods:
    
    - lemma : filters all Word objects with lemma matching our lemma
    """
    def lemma(self, value): return set(i for i in self if i.lemma == value)
    def lang(self, value): return set(i for i in self if i.lang == value)

class FilteredList(list):
    """SetWithFilter but dictionary type"""
    def lemma(self, value): return list(i for i in self if i.lemma == value)
    def lang(self, value): return list(i for i in self if i.lang == value)

# LOADING

def l(lang):
    """
    Language code converter
    
    :param lang (str): language name
    
    :return: conventional language code
    :rtype: str
    """
    if lang in lang_codes: return lang_codes[lang]
    else: return lang

def update(user, password):
    github = Github('dkbrz', 'mandarinka24', verify=False)
    user = github.get_user('apertium')
    repos = list(user.get_repos())
    with open('download.txt', 'w', encoding='utf-8') as f:
        for repo in tqdm(repos):
            try:
                content = repo.get_dir_contents('/')
                for i in sorted(content, key = lambda x: (len(x.path), 1000-ord(('   '+x.path)[-3])), reverse=True):
                    if re.match('apertium-.*?\.[a-z]{2,3}(_[a-zA-Z]{2,3})?-[a-z]{2,3}(_[a-zA-Z]{2,3})?.dix$', i.path): 
                        f.write(i.download_url+'\n')
                        break
                    elif len(i.path) < 23: bidix = None
            except: pass
#                print (repo)

def download():
    if not os.path.exists('./dictionaries/'): os.makedirs('./dictionaries/')
    with open('download.txt', 'r', encoding='utf-8') as f:
        for line in tqdm(f.readlines()):
            bidix = line.strip()
            try:
                filename = './dictionaries/'+bidix.split('/')[-1]
                response = requests.get(bidix)
                response.encoding = 'UTF-8'
                with open(filename, 'w', encoding='UTF-8') as f: f.write(response.text)
            except:
                pass

def list_files(path='./dictionaries/', dialects = False):
    """
    Creates file list that contains all file names of dictionaries
    that need to be considered for preprocessing (some can be excluded
    to avoid unnecessary preprocessing that is quite slow).
    
    Option 1: downloaded dictionaries + no dialects - only list of
    files in 'dictionaries' folder
    
    Option 2: downloaded dictionaries + dialects - list of splitted
    files with dialects + ordinary dictionaries
    
    Option 3: user dictionaries in path + no dialects
    
    Option 4: user dictionaries + dialects - list of files and splitted
    files in 'dictionaries' folder (to avoid damage to real files)
    
    :param path (str): directory in which we search for bilingual
    dictionaries (default - 'dictinaries' folder that is used for downloading)
    :param dialects (boolean): whether split files by dialect or not
    """
    from tool.data import remove
    with open ('filelist.txt','w', encoding='utf-8') as f:
        for root, dirs, files in os.walk (path):
            for file in files:
                if re.match('apertium-.*?\.[a-z]{2,3}(_[a-zA-Z]{2,3})?-[a-z]{2,3}(_[a-zA-Z]{2,3})?.dix$', file):
                    name = '-'.join(l(i) for i in file.split('.')[-2].split('-'))
                    if name not in remove:
                        f.write(os.path.abspath(os.path.join(root, file)).replace("\\","/")+'\n')
    if dialects:
        split_dialects()

def split_dialects():
    """
    Checks all files in folder or path (if path) and splits them on
    different dictionaries for each dialect combination (e.g. nor-nno-nob)
    """
    with open('filelist.txt','r') as f:
        file_list = f.readlines()
    file_list = [i.strip() for i in file_list]
    file_list2 = []
    for file in file_list:
        if not os.path.exists('./dictionaries/'): os.makedirs('./dictionaries/')
        filename = file.split('.')[-2].split('-')
        try:
            tree = ET.parse(file)
            result = {}
            for section in tree.findall('section'):
                for i in section:
                    name = []
                    if not 'vl' in i.attrib and not 'vr' in i.attrib:
                        name = [filename[0]+'-'+filename[1]]
                    elif 'vr' in i.attrib and not 'vl' in i.attrib:
                        name = [filename[0]+'-' + l(filename[1]+'_'+j) for j in i.attrib['vr'].split(' ')]
                    elif 'vl' in i.attrib and not 'vr' in i.attrib:
                        name = [l(filename[0]+'_'+j) +'-'+filename[1] for j in i.attrib['vl'].split(' ')]
                    else:
                        for j in i.attrib['vl'].split(' '):
                            for k in i.attrib['vr'].split(' '):
                                name.append(l(filename[0]+'_'+j)+'-'+l(filename[1]+'_'+k))
                    for j in name:
                        if j not in result: result[j] = ET.Element('section')
                        result[j].append(i)

            if len (result) > 1:
                for i in result:
                    nm = i.split('-')
                    nm = './dictionaries/apertium-{}-{}.{}-{}.dix'.format(filename[0], filename[1], nm[0], nm[1])
                    tree = ET.Element('dictionary')
                    tree.append(result[i])
                    ET.ElementTree(tree).write(nm, encoding='utf-8')
                    with open(nm, 'r', encoding='utf-8') as f:
                        xml = f.read()
                    with open(nm, 'w', encoding='utf-8') as f:
                        f.write(xml.replace('<e','\n    <e').replace('</section>','\n</section>'))    
                    file_list2.append(os.path.abspath(nm).replace("\\","/"))
                print ('-'.join(filename))
            else:
                file_list2.append(file)
        except: pass 
        with open('filelist.txt','w', encoding='utf-8') as f:
            f.write('\n'.join(file_list2))

# PREPROCESSING AND BUILDING

def all_languages():
    """
    Set of all languages in bilingual dictionaries. This set is used
    for monolingual dictionaries.
    """
    s = set()
    with open ('./tool/langs.py','w',encoding='utf-8') as outp:
        with open ('filelist.txt','r',encoding='utf-8') as inp:
            for line in inp:
                name = [l(i) for i in line.split('.')[-2].split('-')]
                s.update(name)
        outp.write('langs='+str(s))

def one_language_dict(lang):
    """
    It gathers all words in all bilingual dictionaries that contain
    this particular language.
    
    :param lang (str): language name
    
    :return: dictionary
    :rtype: FilteredDict
    """
    dictionary = FilteredDict()
    dictionary.set_lang(lang)
    with open ('./filelist.txt','r', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\n')
            pair = [l(i) for i in line.split('.')[-2].split('-')]
            if '-'.join(pair) in rename: pair = rename['-'.join(pair)].split('-')
            if lang in pair:
                if lang == pair[0]: side = 'l'
                else: side = 'r'
                try:
                    with open (line, 'r', encoding='utf-8') as d:
                        t = ET.fromstring(d.read().replace('<b/>',' ').replace('<.?g>',''))
                    for word in parse_one(t, side, lang): dictionary.add(word)
                except: pass
    return dictionary

def shorten(word_dict):
    """
    One of the most important functions. It combines different tags
    for words into one object if they don't contradict. Priority to
    most frequent ones.
    
    If we have 5 dictionaries with 'stol' (Russian word 'table') as 
    n-m and 1 with n-m-sg than tag sequence will be [n-m_n-m-sg]
    because n-m is more likely to be actual and enough while automatic
    tag selection. Moreover, when we have contradicting tags like
    n-f-sg and n-m we have to decide to which one we can write a sole
    'n' in some dictionary.
    
    :param word_dict (WordDict): different tags for lemma
    
    :return: lemma + structured tags
    :rtype: str, list
    """
    short = []
    for i in sorted(word_dict, key=lambda x: (word_dict[x], -len(x)), reverse=True):
        new, add = True, True
        for key, j in enumerate(short):
            if not add: break
            inner = True
            for key2, k in enumerate(j):
                if (k < i) or (i < k): pass
                else: inner = False
            if inner: 
                short[key].append(i)
                new = False
                add = False
        if new: short.append([i])
    word = word_dict.lemma[4:]
    return word, short

def one_word(word, lang):
    """
    One word parsing: lemma, tags, wrap in Word class
    
    :param word (ElementTree): one word from .dix file (left or right
    side)
    :param lang (str): language name
    
    :return: Word object with tags
    :rtype: Word
    """
    if word.text: st = str(word.text)
    else: st = ''
    s = [i.attrib['n'] for i in word.findall('.//s')]
    s = [i for i in s if i != '']
    return Word(st, lang, s)

def parse_one (tree, side, lang):
    """
    Yields all words (Word objects) from one bilingual dictionary.
    
    :param tree (etree.ElementTree): etree.ElementTree object from 
    .dix file
    :param side (str): which side is the language we parse
    :param lang (str): language name
    
    :yield: Word objects of words
    :ytype: Word
    """
    all = tree.findall('section')
    for tree in all:
        for e in tree:
            p = e.find('p')
            if p:
                word = one_word(p.find(side), lang)
                yield word
            else:
                i = e.find('i')
                if i:
                    word = one_word(i, lang)
                    yield word
                else:
                    pass

def dictionary_to_nodes(dictionary):
    """
    Process all word in dictinary (shorten tags and yield all variants)
    
    :param dictionary (FilteredDict): FilteredDict object containing
    all words from this language
    
    :yield: words
    :ytype: Word
    """
    for i in dictionary.keys():
        word, tags = shorten(dictionary[i])
        if '_' in word:
            word = word.replace('_', ' ')
        for tag in tags:
            yield Word(word, dictionary.lang, Tags([i for i in tag if i != '']))

def monodix():
    """
    Creates artificially created monolingual dictionaries with words
    that have all tag variants and ready to be used in bilingual
    dictionary parsing.
    
    For each language in list of languages this function creates a
    dictionary.
    """
    logging.info('Started monolingual dictionaries')
    if not os.path.exists('./monodix/'):
        os.makedirs('./monodix/')
    #for lang in tqdm(langs):
    for lang in langs:
        dictionary = one_language_dict(lang)
        with open ('./monodix/'+lang+'.dix', 'w', encoding = 'utf-16') as f:
            for i in dictionary_to_nodes(dictionary):
                f.write (i.write(mode='mono')+'\n')
    logging.info('Finished monolingual dictionaries')

def check (word1, word2, l1, l2):
    """This function gets word with tags from real bilingual dictionary
    and creates an object (with multiple tags) that matches this word
    (node for graph)
    
    Input: word with one tag variant (n-m). Output: full tags
    (n|n-m|n-m-sg)
    
    :param word1, word2 (str): words
    :param l1, l2 (DiGetItem): dictionaries
    """
    word1 = l1[word1]
    word2 = l2[word2]
    return word1, word2

def one_word2(word, lang):
    """
    One word parsing in bidix
    
    :param word (ElementTree): one word from bidix
    :param lang (str): language name
    """
    s = word.findall('.//s')
    s = [i.attrib['n'] for i in s]
    if word.text: st = str(word.text)
    else: st = ''
    s = Tags(s)
    if '_' in st: st = st.replace('_',' ')
    return Word(st, lang, s)

def parse_bidix (tree, lang1, lang2):
    """
    Bilingual dictionary parsing. Creates a file that contains all word
    pairs from original dictionary but in proper form for a future
    graph.
    
    :param tree (etree.ElementTree): etree.ElementTree object from 
    .dix file
    :param lang1, lang2 (str): language names
    
    :yield: words
    :ytype: Word
    """
    all = tree.findall('section')
    if not all: pass
    else:
        for tree in all:
            for e in tree:
                if 'r' in e.attrib: side = e.attrib['r']
                else: side = ''
                p = e.find('p')
                if p:
                    yield one_word2(p.find('l'), lang1), one_word2(p.find('r'), lang2), side
                else:
                    i = e.find('i')
                    if i:
                        yield one_word2(i, lang1), one_word2(i, lang2), side

def existance(pair, nodes):
    """Check if language pair links two languages from our list.
    
    :rtype: boolean
    """
    if pair[0] in nodes and pair[1] in nodes: return True
    else: return False

def bidix():
    """
    Parsing bilingual dictionaries from file list. Creates all
    preprocessed copies of these dictionaries.
    
    1. Creates 'parsed' folder for these dictionaries.
    2. Creates 'stats' file that will contain information about the
    size of all bilingual dictionaries (this will be used to define
    valuable dictionaries and languages for a graph).
    3. Converts original dictionary into parsed copy.
    4. Counts both, RL and LR words.
    """
    logging.info('Started bilingual dictionaries')
    if not os.path.exists('./parsed/'): os.makedirs('./parsed/')
    with open ('./tool/stats.csv','w',encoding='utf-8') as stats:
        with open('./filelist.txt', 'r', encoding = 'utf-8') as f:
            lines = f.readlines()
        for line in tqdm(lines):
            file = line.strip('\n')
            name = [l(i) for i in line.split('.')[-2].split('-')]
            nm = '-'.join(name)
            if nm in rename: 
                name = [i for i in rename[nm].split('-')]
                #l1 = import_mono(name[1])
                #l2 = import_mono(name[0])
                #print (name)
            #else:
            l1 = import_mono(name[0])
            l2 = import_mono(name[1])
            with open (file, 'r', encoding='utf-8') as d:
                with open ('./parsed/'+'-'.join(name), 'w', encoding='utf-8') as copy:
                    count = [0,0,0]
                    try:
                        tree = ET.fromstring(re.sub('\s{3,}','\t', d.read().replace('<b/>',' ').replace('<.?g>','')))
                        for word1, word2, side in parse_bidix (tree, name[0], name[1]):
                            try:
                                word1, word2 = check (word1, word2, l1, l2)
                                if not side: count[0]+=1
                                elif side == 'LR': count[1] += 1
                                elif side == 'RL': count[2] += 1
                                string = str(side) + '\t' + word1.write(mode='bi') + '\t' + word2.write(mode='bi') + '\n'
                                copy.write(string)
                            except: pass
                    except: pass
                    stats.write('\t'.join(name) + '\t'+ '\t'.join(str(i) for i in count)+'\n')
                    #print ('-'.join(name), end='\t')
    print ()
    logging.info('Finished bilingual dictionaries')

def preprocessing():
    """
    Combination of previous functions: all_languages, monodix and bidix
    """
    all_languages()
    global langs
    from .langs import langs
    monodix()
    bidix()

def import_mono(lang):
    """
    Reads artificial monodix and creates a dictionary with all word in 
    this language.
    
    :param lang (str): language name
    
    :return: dictionary
    :rtype: DiGetItem 
    """
    dictionary = DiGetItem()
    with open ('./monodix/{}.dix'.format(lang), 'r', encoding='utf-16') as f:
        for line in f:
            string = line.strip('\n').split('\t')
            s = [Tags([j for j in i.split('-') if j !='']) for i in string[1].strip().split('$')]
            dictionary.add(Word(string[0], lang, s))
    return dictionary

# BUILDING

def get_relevant_languages(lang1, lang2):
    """
    Recommendations for choosing best languages to include in graph.
    
    Graph:
    
    - nodes - languages
    - edges - weighted existing bilingual dictionaries
    
    Weights:
    
    EdgeWeight = 1 / log10(both_sides + 0.5*LR + 0.5*RL)
    
    In this graph we take 300 best (shortest) paths between 2 languages
    and those languges that occur in these paths are recommended. They
    are sorted in order of length of the best path in which they occur.
    
    Example: eng-spa
    
    ```
    0.22082497988083025	eng	:	eng spa
    0.22082497988083025	spa	:	eng spa
    0.4250627830992572	cat	:	eng cat spa
    0.44444829199452307	epo	:	eng epo spa
    ...
    0.6661607856269738	nor	:	eng nor ita spa
    0.66687498614133	arg	:	eng cat arg spa
    ...
    1.0200843703377707	sme	:	eng fin sme eus spa
    1.0451794809559942	cos	:	eng ita cos spa
    1.0551281116166376	dan	:	eng nor dan deu spa
    ```
    
    
    :param lang1, lang2 (str): language names
    """

    G = nx.Graph()
    with open ('./tool/stats.csv', 'r', encoding='utf-8') as f:
        for line in f:
            data = line.split('\t')
            coef = 1/log10(10+float(data[2])+0.5*float(data[3])+0.5*float(data[4]))
            if coef < 1:
                G.add_edge(data[0], data[1], weight=coef)
    result = {}
    for path in islice(nx.shortest_simple_paths(G, source=lang1, target=lang2, weight='weight'), 0, 300):
        length = sum([G[path[i]][path[i-1]]['weight'] for i in range(1, len(path))])
        for node in path:
            if node not in result:
                result[node]  = (length, path)
    config = '{}-{}-config'.format(lang1, lang2)
    with open (config,'w', encoding='utf-8') as f:
        for i in sorted(result, key=result.get):
            f.write(str(result[i][0])+'\t'+str(i)+'\t:\t'+' '.join(result[i][1])+'\n')

def load_file(lang1, lang2, n=10):
    """
    It takes top-N languages from configuration file and merges
    bilingual dictionaries (preprocessed) with both languages in short
    list (configuration file).
    
    :param lang1, lang2 (str): languge names
    :param n (int): number of languages we want to use in graph
    """
    with open ('{}-{}-config'.format(lang1, lang2),'r',encoding='utf-8') as f:
        languages = set([i.split('\t')[1].strip() for i in islice(f.readlines(), 0, n)])
    languages = languages | set([lang1,lang2])
    file = '{}-{}'.format(lang1, lang2)
    with open (file, 'w', encoding='utf-16') as f:
        for root, dirs, files in os.walk ('./parsed/'):
            for fl in files:
                pair = fl.replace('.dix','').split('-')
                if existance(pair, languages):
                    #print (pair)
                    with open (root+fl, 'r', encoding='utf-8') as d:
                        f.write(d.read())
    with open(file, 'r', encoding='utf-16') as f:
        text = f.read()
    text = text.encode('utf-8')
    text = text.decode('utf-8')
    with open(file, 'w', encoding='utf-8') as f:
        f.write(text)

def parse_line(line):
    """
    It parses line in loading file (with edges) and returns side (LR,
    RL, both) and two Word objects.
    
    :param line (str): line in a loading file (translation, pair of
    words)
    
    :return: side, word1, word2
    :rtype: str, Word, Word
    """
    side, lang1, lemma1, tags1, lang2, lemma2, tags2 = line.strip('\n').split('\t')
    tags1 = [Tags(i.split('-')) for i in tags1.split('$')]
    tags2 = [Tags(i.split('-')) for i in tags2.split('$')]
    return side, Word(lemma1, lang1, tags1), Word(lemma2, lang2, tags2)

def built_from_file(file):
    """
    This function returns a graph based on loading file (this graph
    will be used in further ditionary enrichment)
    
    :param file (str): filename
    
    :return: result graph with all words
    :rtype: NetworkX.DiGraph
    """
    G = nx.DiGraph()
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            side, word1, word2 = parse_line(line)
            if not side:
                G.add_edge(word1, word2)
                G.add_edge(word2, word1)
            elif side == 'LR': G.add_edge(word1, word2)
            elif side == 'RL': G.add_edge(word2, word1)
            else: pass #print (side)
    return G

def dictionaries(lang1, lang2):
    """
    Returns two dictionaries (from pair we want to enrich) as
    SetWithFilter. So we can go through all words and create
    suggestions about possible translations.
    
    :param lang1, lang2 (str): language names
    
    :return: dictionaries
    :rtype: SetWithFilter
    """
    l1 = import_mono(lang1)
    l2 = import_mono(lang2)
    l1 = SetWithFilter(l1.list+list(l1.dict.keys()))
    l2 = SetWithFilter(l2.list+list(l2.dict.keys()))
    return l1, l2

def check_graph(lang1, lang2, n=10):
    """
    Probably only for ipynb. Shows graph of languages that will be
    included in graph (languages and bilingual dictionaries).
    
    :param lang1, lang2 (str): language names
    :param n (int): number of languages we eant to use in graph
    """
    G = nx.Graph()
    with open ('./tool/stats.csv', 'r', encoding='utf-8') as f:
        for line in f:
            data = line.split('\t')
            coef = 1/log10(10+float(data[2])+0.5*float(data[3])+0.5*float(data[4]))
            if coef < 1:
                G.add_edge(data[0], data[1], weight=coef)
    with open ('{}-{}-config'.format(lang1, lang2),'r',encoding='utf-8') as f:
        languages = set([i.split('\t')[1].strip() for i in islice(f.readlines(), 0, n)])
    languages = languages | set([lang1,lang2])
    nx.draw_shell(G.subgraph(languages), with_labels = True, font_size = 20, node_color = 'white')

# SEARCH

def metric(G, word, translation, cutoff, mode='exp'):
    """
    Evaluates translation (word+translation).
    
    coefficient = sum(exp^(-i)), i - length of path from all simple
    paths between word and translation with set cutoff.
    
    :param G (NetworkX.DiGraph): graph
    :param word (Word): node in graph (word)
    :param translation (Word): one translation variant
    :param cutoff (int): cutoff in graph
    
    :return: coefficient
    :rtype: float
    """
    coef = 0
    if mode == 'exp':
        t = Counter([len(i) for i in nx.all_simple_paths(G, word, translation, cutoff=cutoff)])
        for i in t: 
            coef += exp(-i)*t[i]
        return coef

def _single_shortest_path_length(adj, firstlevel, cutoff, lang):
    """
    Variant of NetworkX function _single_shortest_path_length
    
    Yields all possible translations with     cutoff. 
    
    Cutoff: n steps from source node + stops when target language node
    occur or there are more then 10 variants (less then 10 + next
    level(cutoff))
    
    :param adj : special NetworkX type of graph representation
    :param firstlevel (dict): starting nodes
    :param cutoff (int): cutoff
    :param lang (str): target language
    
    :return: list of candidates
    :rtype: list
    """
    seen = {}                  # level (number of hops) when seen in BFS
    level = 0                  # the current level
    nextlevel = firstlevel     # dict of nodes to check at next level
    result = []
    while nextlevel and cutoff >= level and len(result) < 10:
        thislevel = nextlevel  # advance to next level
        nextlevel = {}         # and start a new list (fringe)
        for v in thislevel:
            if v not in seen:
                seen[v] = level  # set the level of vertex v
                if v.lang == lang: result.append(v)
                else: nextlevel.update(adj[v])
        level += 1
    return result

def possible_translations(G, source, lang, cutoff=4):
    """
    Wrapper for previous _single_shortest_path_length function
    
    :param G (NetworkX.DiGraph): graph
    :param source (Word): node (word)
    :param cutoff (int): cutoff
    :param lang (str): target language
    
    :return: list of candidates
    :rtype: list
    """
    if source not in G: raise nx.NodeNotFound('Source {} is not in G'.format(source))
    if cutoff is None: cutoff = float('inf')
    nextlevel = {source: 0}
    return _single_shortest_path_length(G.adj, nextlevel, cutoff, lang)

def evaluate(G, word, candidates, cutoff=4, topn=None):
    """
    Evaluates candidates from possible translations.
    
    Options:
    
    1. topn - returns top-N candidates
    2. "auto" - relevant candidates
    
    "auto"
    
    If there are 10+ candidates returns those that have coefficient
    more than average. Usually there are top variants and other
    variants have very low coefficient. So it filters relevant
    candidates based on particular case coefficients
    
    If there are less than 10 candidates, adds coefficients with
    minimal coefficient to get more reliable data. And then it returns
    same top candidates.
    
    :param G (NetworkX.DiGraph): graph
    :param word (Word): node (word)
    :param candidates (list): list of candidates
    :param cutoff (int): cutoff
    :param topn (None, int): how many best candidates we want to get
    (None for 'auto' mode, int for certain number)
    
    :return: sorted list of translations and coefficients
    :rtype: list
    """
    result = {}
    mean = 0
    for translation in candidates:
        result[translation] = metric(G, word, translation, cutoff=cutoff)
        mean += result[translation]
    result = [(x, result[x]) for x in sorted(result, key=result.get, reverse=True)]
    if topn: return result[:topn]
    else:
        result = result[:10]
        if len(result) < 10: 
            mean += exp(-cutoff-1)*(10-len(result))
        mean = mean / 10
        result = [x for x in result if x[1] > mean]
        return result

def lemma_search (G, lemma, d_l1, lang2, cutoff=4, topn=None):
    lemmas = [i for i in d_l1.lemma(lemma) if i in G.nodes()]
    results = {word:{} for word in lemmas}
    for word in lemmas:
        candidates = possible_translations(G, word, lang2, cutoff=cutoff)
        results[word] = evaluate(G, word, candidates, cutoff=cutoff, topn=topn)
        del candidates
    return results

# EVALUATION

def node_search(G, node, lang2, cutoff=4, topn=None):
    """
    Returns translations (without coefficients) for a particular node
    using possible_translations and evaluate functions.
    
    :param G (NetworkX.DiGraph): graph
    :param node (Word): node (word)
    :param lang2 (str): target language
    :param cutoff (int): cutoff
    :param topn (None, int): how many best candidates we want to get
    (None for 'auto' mode, int for certain number)
    
    :return: sorted list of translations
    :rtype: list
    """
    if node not in G.nodes(): return None
    candidates = possible_translations(G, node, lang2, cutoff=cutoff)
    results = evaluate(G, node, candidates, cutoff=cutoff, topn=topn)
    return [i[0] for i in results]

def two_node_search (G, node1, node2, lang1, lang2, cutoff=4, topn=None):
    """
    Evaluation of pair of real translations.
    
    LR: if the right one is in translations and index < topn +0.5,
    index >= topn +0.01
    
    The same for RL side.
    
    1: both sides right
    
    0: both sides wrong
    
    (0,1): there is some truth but not perfect translation
    
    :param G (NetworkX.DiGraph): graph
    :param node1, node2 (Word): nodes (two words)
    :param lang1, lang2 (str): languages
    :param cutoff (int): cutoff
    :param topn (None, int): mode for top-N candidates (None for 'auto'
    mode, int for certain number)
    
    :return: coefficient
    :rtype: float
    """
    if (node1, node2) in G.edges(): G.remove_edge(node1, node2)
    if (node2, node1) in G.edges(): G.remove_edge(node2, node1)
    res1 = node_search(G, node1, lang2, cutoff=cutoff, topn=topn)
    res2 = node_search(G, node2, lang1, cutoff=cutoff, topn=topn)
    coefficient = 0
    if not topn: topn = 1000
    if node2 in res1: 
        pos = res1.index(node2)
        if pos < topn: coefficient += 0.5
        else: coefficient += 0.01
    if node1 in res2: 
        pos = res2.index(node1)
        if pos < topn: coefficient += 0.5
        else: coefficient += 0.01
    return coefficient

def _one_iter(lang1, lang2, G, l1, cutoff=4, topn=None):
    """
    One iteration of evaluation.
    
    1. Select up to 1000 random mutually unambiguous pairs.
    2. Evaluate with two_node_search
    3. Calculate precision, recall, f1
    
    # all perfect to perfect+non-zero
    precision = sum(1 for i in result if i == 1) / 
                sum(1 for i in result if i > 0)
    # all perfect to all
    recall = sum(1 for i in result if i == 1) /
             sum(1 for i in result)
    # usual f1
    f1 = 2 * precision * recall / (precision + recall)
    
    :param lang1, lang2 (str): languages
    :param G (NetworkX.DiGraph): graph
    :param l1 (SetWithFilter): dictionary
    :param cutoff (int): cutoff
    :param topn (None, int): mode for top-N candidates
    (None for 'auto' mode, int for certain number)
    """
    candidates = random.sample(l1, len(l1))
    pairs = []
    for i in candidates:
        if len(pairs) < 1000 and i in G.nodes():
            ne = list(G.neighbors(i))
            s = FilteredList(ne).lang(lang2)
            if len(s) == 1 and len(ne) > 1:
                ne = list(G.neighbors(s[0]))
                if len(FilteredList(ne).lang(lang1)) == 1 and len(ne)>1 and FilteredList(ne).lang(lang1)[0]==i:
                    pairs.append((i, s[0]))
        elif len(pairs) >= 1000: break
    if len(pairs) == 0: print ('no one-variant')
    pairs2 = pairs[:1000]
    result = []
    for i in tqdm(pairs): 
        result.append(two_node_search (G, i[0], i[1], lang1, lang2, cutoff=cutoff, topn=topn))
    print ('N='+str(len(pairs2)))
    try:
        precision = sum(1 for i in result if i == 1) / sum(1 for i in result if i > 0)
        recall = sum(1 for i in result if i == 1) / sum(1 for i in result)
        f1 = 2 * precision * recall / (precision + recall)
        print ('Precision : {}, recall : {}, f1-score : {}'.format(precision, recall, f1))
    except:
        print ('error')
    del G, pairs

def eval_loop(lang1, lang2, n=10, topn=None, n_iter=3, cutoff=4):
    """
    Calculates precision, recall and f1 for language pair.
    
    :param lang1, lang2 (str): languages
    :param n (int): number of best languages to use in graph
    :param topn (None, int): mode for top-N candidates
    (None for 'auto' mode, int for certain number)
    :param n_iter (int): how many iterations of evaluation
    :param cutoff (int): cutoff
    """
    logging.info('Start ~ 20 s')
    n, cutoff, n_iter = int(n), int(cutoff), int(n_iter)
    if topn: topn = int(topn)
    get_relevant_languages(lang1, lang2)
    load_file(lang1, lang2, n=n)
    l1, l2 = dictionaries(lang1, lang2)
    #k = len(l1)
    #if k > 10000: k =10000
    #elif k < 1000: return 'less than 1000'
    #else: k = len(l1)
    for i in range(n_iter):
        logging.info('Initialization '+str(i+1)+' ~ 1 min')
        G = built_from_file('{}-{}'.format(lang1,lang2))
        _one_iter(lang1, lang2, G, l1, cutoff=cutoff, topn=topn)

#def change_encoding(file):
#    "Change utf-16 that works with accents inside program to utf-8 to reduce file size (doesn't cause problems in this case)"
#    with open(file, 'r', encoding='utf-16') as f:
#        text = f.read()
#    text = text.encode('utf-8')
#    text = text.decode('utf-8')
#    with open(file, 'w', encoding='utf-8') as f:
#        f.write(text)

def addition(lang1, lang2, n=10, cutoff=4):
    """
    How many entries we can add LR and RL side (both only after merging
    - in a real file)
    
    :param lang1, lang2 (str): languages
    :param n (int): number of best languages to use in graph
    :param n_iter (int): how many iterations of evaluation
    :param cutoff (int): cutoff
    """
    logging.info('Initialization ~ 1 min')
    get_relevant_languages(lang1, lang2)
    load_file(lang1, lang2, n=n)
    #change_encoding('{}-{}'.format(lang1,lang2))
    G = built_from_file('{}-{}'.format(lang1,lang2))
    l1, l2 = dictionaries(lang1, lang2)
    k1, k2 = [0,0,0,0], [0,0,0,0] #existant, failed, new, errors
    for node in tqdm(l1):
        if node in G:
            s = FilteredList(list(G.neighbors(node))).lang(lang2)
            if not len(s):
                candidates = possible_translations(G, node, lang2, cutoff=cutoff)
                if candidates: k1[2] += 1
                else: k1[1] += 1
            else: k1[0] += 1
        else: k1[3] +=1
    if k1[0] > 0: c = k1[2]/k1[0]*100
    else: c = 0
    print ('{}->{}    Exist: {}, failed: {}, NEW: {} +{}%, NA: {}'.format(lang1, lang2, k1[0], k1[1], k1[2], round(c, 0), k1[3]))
    
    for node in tqdm(l2):
        if node in G:
            s = FilteredList(list(G.neighbors(node))).lang(lang1)
            if not len(s):
                candidates = possible_translations(G, node, lang1, cutoff=cutoff)
                if candidates: k2[2] += 1
                else: k2[1] += 1
            else:
                k2[0] += 1
        else: k2[3] += 1
    if k2[0] > 0: c = k2[2]/k2[0]*100
    else: c = 0
    print ('{}->{}    Exist: {}, failed: {}, NEW: {} +{}%, NA: {}'.format(lang2, lang1, k2[0], k2[1], k2[2], round(c, 0), k2[3]))

#def generate_example(l1, G, lang2):
#    for i in l1:
#        if i in G:
#            ne = list(G.neighbors(i))
#            s = FilteredList(ne).lang(lang2)
#            if len(s) == 0:
#                candidates = possible_translations(G, i, lang2, cutoff=4)
#                result = evaluate(G, i, candidates, cutoff=4)
#                if result: yield i, result

def get_translations(lang1, lang2, cutoff=4, topn=None):
    """
    Steps:
    1. Loading dictionaries
    2. Building graph
    3. Searching for non-existent translations
    4. Writing preview file (for human assessment)
    
    :param lang1, lang2 (str): languages
    :param n (int): number of best languages to use in graph
    :param n_iter (int): how many iterations of evaluation
    :param cutoff (int): cutoff
    """
    logging.info('Initialization (~1 min)')
    G = built_from_file('{}-{}'.format(lang1,lang2))
    l1, l2 = dictionaries(lang1, lang2)
    RESULT = {}
    for i in tqdm(l1):
        if i in G:
            ne = list(G.neighbors(i))
            s = FilteredList(ne).lang(lang2)
            if len(s) == 0:
                candidates = possible_translations(G, i, lang2, cutoff=4)
                result = evaluate(G, i, candidates, cutoff=4)
                if result:
                    for j in result: RESULT[(i, j[0])] = [j[1], 0]
    for i in tqdm(l2):
        if i in G:
            ne = list(G.neighbors(i))
            s = FilteredList(ne).lang(lang1)
            if len(s) == 0:
                candidates = possible_translations(G, i, lang1, cutoff=4)
                result = evaluate(G, i, candidates, cutoff=4)
                if result:
                    for j in result: 
                        if (j[0], i) in RESULT: RESULT[(j[0], i)][1] = j[1]
                        else: RESULT[(j[0], i)] = [0, j[1]]
    with open('{}-{}-preview'.format(lang1, lang2),'w',encoding='utf-8') as f:
        for i in sorted(RESULT):
            s = i[0].write(mode='out')+'\t'+i[1].write(mode='out')+'\t'+str(RESULT[i][0])+'\t'+str(RESULT[i][1])+'\n'
            f.write(s)

def parse_preview_line(line, lang1, lang2):
    """
    Subfunction to the one below. It parses a line in a preview file
    and returns side + 2 Word objects
    
    :param line (str): line from preview file (pair of translations)
    :param lang1, lang2 (str): languages
    
    :return: side, word1, word2
    :rtype: str, Word, Word
    """
    lemma1, tags1, lemma2, tags2, n1, n2 = line.strip('\n').split('\t')
    tags1 = tags1.split('-')
    tags2 = tags2.split('-')
    side = None
    if float(n1) > 0 and float(n2) == 0: side = 'RL'
    elif float(n1) == 0 and float(n2) > 0: side == 'LR'
    return side, Word(lemma1, lang1, tags1), Word(lemma2, lang2, tags2)

def convert_to_dix(lang1, lang2):
    """
    Converting preview file into section for usual .dix file.
    
    :param lang1, lang2 (str): languages
     """
    tree = ET.Element('section')
    with open ("{}-{}-preview".format(lang1, lang2),'r', encoding='utf-8') as inp:
        for line in inp:
            side, word1, word2 = parse_preview_line(line, lang1, lang2)
            if side: pair = ET.Element('e', {'r':side})
            else: pair = ET.Element('e')
            p = ET.SubElement(pair, 'p')
            l = ET.SubElement(p, 'l')
            r = ET.SubElement(p, 'r')
            l.text = word1.lemma
            r.text = word2.lemma
            for i in word1.s: 
                if i: l.append(ET.Element('s', {'n':i}))
            for i in word2.s: 
                if i: r.append(ET.Element('s', {'n':i}))
            tree.append(pair)
    ET.ElementTree(tree).write("{}-{}-new".format(lang1, lang2), encoding='utf-8')
    with open("{}-{}-new".format(lang1, lang2), 'r', encoding='utf-8') as f:
        xml = f.read()
    with open("{}-{}-new".format(lang1, lang2), 'w', encoding='utf-8') as f:
        f.write(xml.replace('<e','\n    <e').replace('</section>','\n</section>'))

def merge(lang1, lang2):
    """
    Merging files with different dialects. All languages or dialects
    are written in vr and vl tags.
    
    :param lang1, lang2 (str): languages
     """
    with open ('{}-{}-merged'.format(lang1[0].upper(), lang2[0].upper()), 'w', encoding='utf-8') as result:
        for i in lang1:
            for j in lang2:
                with open("{}-{}-new".format(i, j), 'r', encoding='utf-8') as f:
                    text = f.read()
                    if len(i.split('_')) > 1: i = '_'.join(i.split('_')[1:])
                    if len(j.split('_')) > 1: j = '_'.join(j.split('_')[1:])    
                    text = text.replace('<e', '<e vl=\'{}\' vr=\'{}\' '.format(i, j))
                    result.write(text + '\n\n')

## EXAMPLES
def print_lemma_results(results, file):
    for i in results:
        print ('\t\t', i, file=file)
        for j in results[i]:
            print ('{}\t{}'.format(j[0], j[1]), file=file)
        print('', file=file)

def example (lang1, lang2, n=10, cutoff=4, topn=None, input='', lang = '', config=False, load=False, output=''):
    """
    
    
    """
    logging.info('Initialization ~1 min')
    if output: file = open(output, 'w', encoding='utf-8')
    else: output = sys.stdout
    with open (input, 'r', encoding='utf-8') as f:
        words = f.read().split()
    if config:
        get_relevant_languages(lang1, lang2)
        logging.info('languages')
    if load: 
        load_file(lang1, lang2, n=n)
        logging.info('loading file')
    G = built_from_file('{}-{}'.format(lang1,lang2))
    l1, l2 = dictionaries(lang1, lang2)
    logging.info('Translating')
    if lang == lang1:
        for word in tqdm(words):
            print('Lemma: '+word, file=file)
            print_lemma_results(lemma_search (G, word, l1, lang2, cutoff=cutoff, topn=topn), file=file)
            print('---------------------------------------------', file=file)
    elif lang == lang2:
        for word in tqdm(words):
            print('Lemma: '+word, file=file)
            print_lemma_results(lemma_search (G, word, l2, lang1, cutoff=cutoff, topn=topn), file=file)
            print('---------------------------------------------', file=file)
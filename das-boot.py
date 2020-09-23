#!/usr/bin/env python
# coding: utf-8

# In[1]:


max_price=500000
debug=False


# In[2]:


import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
import pickle
from datetime import date

cache_filename = 'page_cache-'+date.today().isoformat()+'.pickle'
page_cache = {}
try:
    with open(cache_filename, 'rb') as f:
        page_cache = pickle.load(f)
except FileNotFoundError:
    print(cache_filename+' not found, starting fresh')

def memoize(f):
    memo = {}
    def helper(x):
        if x not in memo:            
            memo[x] = f(x)
        return memo[x]
    return helper


# In[3]:


import functools

def none_on_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if debug: print(func.__name__+' FAILED with '+str(e))
            return None
    return wrapper
    
def save_obj(obj, name):
    with open(cache_filename, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def get_page(url):
    if url not in page_cache:
        r = requests.get(url, allow_redirects=False)
        if r.status_code == 200:
            page = r.text
            page_cache[url] = page
            return page
        else:
            print('GOT '+str(r.status_code)+' for GET '+url)
            print(r.headers)
            return ''
    return page_cache[url]

def make_soup(url):
    return BeautifulSoup(
        get_page(url),
        'html.parser')

if debug: get_soup = make_soup
else: get_soup = memoize(make_soup)


# In[4]:


# Nettivene.com

re_loa = re.compile(r'(\D*)([\d\.\,]+)(\D*)')

@none_on_error
def nv_price(s):
    return float(s.replace(' ','').replace('€',''))

@none_on_error
def nv_loa(url):
    soup = get_soup(url)
    str_loa = soup.find('td',string='Length').next_sibling.next_sibling.text
    return float(
        re.match(
            re_loa,
            str_loa
        ).group(2).replace(',','.')
    )

@none_on_error
def nv_year(parent_div):
    y_str = re.search(
        r'(\d\d\d\d)',
        parent_div.text
    ).groups()[0]
    return int(y_str)

@none_on_error
def nv_country(s):
    s = s.split()[0]
    if s in (
        'Estonia',
        'Sweden',
        'Lithuania',
        'Spain',
        'Italy',
        'France',
        'Portugal',
        'Greece',
        'Croatia',
        'Germany'
    ): return s.strip()
#    if s not in ('Helsinki','Espoo','Turku','Raisio'): print(s+' presumed to be in Finland')
    return 'Finland'

@none_on_error
def nv_next_page_url(soup):
    return soup.find(
            'a',
            class_='pageNavigation next_link'
        )['href']

def nv_parse_list_page(make,soup):    
    urls = [
        a['href'] 
        for a in soup.findAll('a',class_='childVifUrl')
    ]
    models = [
        div.text.replace(make,'').strip()
        for div in soup.findAll('div',class_='make_model_link')
    ]
    years = [
        nv_year(div) 
        for div in soup.findAll('div',class_='vehicle_other_info clearfix_nett')
    ]
    lengths = [
        nv_loa(url) 
        for url in urls
    ]
    locs = [
        nv_country(div.b.text) 
        for div in soup.findAll('div',class_='location_info')
    ]
    prices = [
        nv_price(div.text) 
        for div in soup.findAll('div',class_='main_price')
    ]

    return list(
        zip(
            urls,
            models,
            years,
            lengths,
            locs,
            prices,
        )
    )

def nv_listings(make):
    next_url = 'https://www.nettivene.com/en/purjevene/'+make.replace(' ','-').lower()
    l = []
    while next_url:
        soup = get_soup(next_url)
        l += nv_parse_list_page(
            make,
            soup
        )
        next_url = nv_next_page_url(soup)
    return l


# In[5]:


#yachtworld

import json
import pycountry

@none_on_error
def yw_redux_state_json(soup):
    script_tag = soup.find('script',string=re.compile('__REDUX_STATE__')).contents[0]
    json_str = script_tag[script_tag.index('window.__REDUX_STATE__ = ')+25:script_tag.rfind('}')+1]
    return json.loads(json_str)    

@none_on_error
def yw_price(record):
    return record['price']['type']['amount']['EUR']

def yw_country(record):
    cc = record['location']['countryCode']
    country = pycountry.countries.get(alpha_2=cc)
    if country: return country.name
    return cc

def yw_collect_listings(js):
    records = js['search']['searchResults']['search']['records']
    return [
        (
            r['mappedURL'],
            r['model'],
            r['year'],
            r['boat']['specifications']['dimensions']['lengths']['nominal']['m'],
            yw_country(r),
            yw_price(r)
        ) for r in records
    ]

def yw_has_next(js):
    curr_page = int(js['search']['searchResults']['search']['currentPage'])
    last_page = int(js['search']['searchResults']['search']['lastPage'])
    return (curr_page<last_page)    


def yw_listings(make):
    url_template='https://www.yachtworld.com/boats-for-sale/condition-used/type-sail/make-{}/?currency=EUR&price=0-{}'
    base_url = url_template.format(make,max_price)
    url = base_url

    l = []
    page = 1
    while True:
        js = yw_redux_state_json(get_soup(url))
        if js:
            l += yw_collect_listings(js)
        
            if yw_has_next(js):
                page += 1
                url = base_url+'&page='+str(page)
            else: break
        else: break
        
    return l


# In[6]:


#boat24

@none_on_error
def parse_b24_price(s):
    return float(''.join(re.findall(r'\d+', s)))
    
@none_on_error
def parse_b24_loa(details_str):
    loa_str = re.search(
            r'([\d\.]+) x .*',
            details_str
        ).groups()[0]
    return float(loa_str)

@none_on_error
def b24_country(s):
    return s.split()[0]

def b24_scrape(make,soup):    
    
    divs = soup.findAll('div', class_='bd')
    
    urls = [
        div.h5.a['href']
        for div in divs
    ]
    models = [
        div.h5.a['title'].replace(make,'').strip()
        for div in divs
    ]
    years = [
        int(t.next_sibling) 
        for t in soup.findAll('label',string='Year Built')
    ]
    lengths = [
        parse_b24_loa(div.text) 
        for div in soup.findAll('div',class_='details')
    ]
    locs = [
        b24_country(div.text) 
        for div in soup.findAll('div',class_='location')
    ]
    prices = [
        parse_b24_price(t.contents[0]) 
        for t in soup.findAll('p',class_='price')
    ]
    
    return list(
        zip(
            urls,
            models,
            years,
            lengths,
            locs,
            prices,
        )
    )
    
@none_on_error
def b24_next_url(soup):
    return soup.find('a', class_='next')['href']

def b24_listings(make):
    next_url = 'https://www.boat24.com/en/sailboats/?src={}&mode=AND&whr=EUR&prs_min=&prs_max={}'.format(
        make.replace(' ','+'),
        max_price
    )
    l = []
    while next_url:
        soup = get_soup(next_url)
        l += b24_scrape(make,soup)
        next_url = b24_next_url(soup)
    return l


# In[14]:


#yachtmarket

@none_on_error
def loa_from(s):
    return float(s.replace('m',''))

@none_on_error
def price_from(s):
    return int(s.replace('€','').replace('EUR','').replace(',','').strip())


def ym_scrape(make, soup):

    anchors = soup.findAll('a',class_='boat-name')

    urls = [
        'https://www.theyachtmarket.com/'+a['href'].split(sep='?')[0] for a in anchors
    ]
    
    pattern = re.compile(make, re.IGNORECASE)
    models = [pattern.sub('', a.text).strip() for a in anchors]

    overviews = [div.text.split('|') for div in soup.findAll('div',class_='overview')]

    years = [int(o[0]) for o in overviews]

    lengths = [loa_from(o[1]) for o in overviews]

    locs = [div.text.split(',')[-1].strip() for div in soup.findAll('div',class_='location')]

    prices = [price_from(div.span.text) for div in soup.findAll('div',class_='pricing')]
    
    return list(
        zip(
            urls,
            models,
            years,
            lengths,
            locs,
            prices,
        )
    )

@none_on_error
def ym_next_url(soup):
    return 'https://www.theyachtmarket.com/en/boats-for-sale/search/'+soup.find('a', rel='next')['href']

def ym_listings(make):
    next_url = 'https://www.theyachtmarket.com/en/boats-for-sale/search/?manufacturermodel={}&currency=eur&lengthunit=metres&showsail=1'.format(
            make.replace(' ','+').lower()
        )
    
    l = []
    while next_url:
        soup = get_soup(next_url)
        l += ym_scrape(make,soup)
        next_url = ym_next_url(soup)
    return l


# In[8]:


def scrape_listings(make):
    nv = nv_listings(make)
    yw = yw_listings(make)
    b24 = b24_listings(make)
    ym = ym_listings(make)
    
    df = pd.DataFrame(nv+yw+b24+ym,columns=['url','model','year','loa','location','price'])
    df.to_csv('listings-'+make.replace(' ', '_').lower()+'.csv')
    
    df = df.round({
        'year': 0,
        'loa': 2,
        'price': 0
    })

    return df


if debug: listings_make = scrape_listings
else: listings_make = memoize(scrape_listings)
    


# In[9]:


from forex_python.converter import CurrencyRates
fx = CurrencyRates()

def sb_history(make,model):
    make = make.lower().replace(' ','-')
    model = model.lower().replace(' ','-')
    url = 'https://www.sokbat.se/Modell/{}/{}'.format(make,model)
    page = get_page(url)
    item_id = re.search(r'CurentItemId = (\d+);',page).group(1)
    str_json = requests.post('https://www.sokbat.se/DataBase/GetPrices?itemId='+item_id).text
    
    df = pd.read_json(str_json[8:-1],orient='records')
    
    df['age'] = df.SalesYear.astype(int) - df.ItemYear.astype(int)
    df['price_sek'] = df.SalesPrice.str.replace(re.compile(r'\s'), '')
    df['price_eur'] = df.price_sek.astype(float) * fx.get_rate('SEK', 'EUR')
    
    return sns.lmplot(x="age", y="price_eur", data=df[df.ItemYear > 0], robust=True)


# In[10]:


ba_re_year_sold = re.compile(r'Sold: (\d\d\d\d-\d\d-\d\d)')
@none_on_error
def ba_date_sold(td):
    return date.fromisoformat(re.search(ba_re_year_sold,td.font.text).group(1))

ba_re_price = re.compile(r'(\d[\d\s]+)\sEUR')
@none_on_error
def ba_price(td):
    return int(re.search(ba_re_price,td.p.text).group(1).replace(u'\xa0', ''))

def ba_listings(make):
    soup = get_soup('http://www.boatagent.com/?sajt=kopbat_sokmotor&sokord='+make.lower().replace(' ','+'))
    tds = soup.findAll('td', class_='batkatalog')
    
    urls = ['http://www.boatagent.com'+td.a['href'] for td in tds]
    
    models = [td.h2.text.replace(make,'') for td in tds]
    
    re_year = re.compile(r'Year of production: (\d\d\d\d)')
    years = [re.search(re_year,td.p.text).group(1) for td in tds]
    
    dates_sold = [ba_date_sold(td) for td in tds]
        
    prices = [ba_price(td) for td in tds]
    
    df = pd.DataFrame(data=list(zip(urls,models,years,dates_sold,prices)),columns=['url','model','year','date_sold','price',])
    
    #df['age'] = df.year - df.date_sold.dt.year
    
    return df


# In[11]:


from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns

a4_landscape = (11.7, 8.27)
a4_portrait = (8.27,11.7)
    
def scatter(df,x,size,ax=None):
    if not ax: fig, ax = plt.subplots(figsize=a4_landscape)
    ax = sns.scatterplot(
        ax=ax, 
        data=df, 
        x=x, 
        y='price',
        size=df[size].tolist(), #https://github.com/mwaskom/seaborn/issues/2194
        hue=df.location.tolist(), #https://github.com/mwaskom/seaborn/issues/2194
#        sizes=(40, 400),
        alpha=.5,
        palette="muted"
    )
    ax.legend(loc='center left', bbox_to_anchor=(1.25, 0.5), ncol=1)
    return ax

def scatter_year(df,ax=None):
    return scatter(df,'year','loa',ax)

def scatter_loa(df,ax=None):
    return scatter(df,'loa','year',ax)


import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning

def regplot(df,ax=None):
    if not ax: fig, ax = plt.subplots(figsize=a4_landscape)    
    warnings.simplefilter('ignore', ConvergenceWarning)
    return sns.regplot(ax = ax, x="year", y="price", data=df, robust=True);


# In[12]:


def listings(make, model=None, min_year=None, max_year=None, min_loa=None, max_loa=None):
    df = listings_make(make)
    
    if min_year: df = df[df.year >= min_year]
    if max_year: df = df[df.year <= max_year]
    if min_loa: df = df[df.loa >= min_loa]
    if max_loa: df = df[df.loa <= max_loa]
        
    if model: df = df[df.model.str.contains(model,case=False)]
        
    return df.sort_values(by='price')

def url_to_html_anchor(url):
    return '<a target="_blank" href="{}">{}</a>'.format(url,url)

def diplay_listings(df):
    display(df.style.format(
        {
            'url': url_to_html_anchor,
            'year': '{:n}',
            'loa': '{:.2f} m',
            'price': '{:n} €',
        }
    ))

def summary(df):
    display(
        df.groupby('model').count()[['url']].rename(columns={'url':'count'})
    )
    fig, (ax1, ax2) = plt.subplots(2,1, figsize=a4_portrait)
    scatter_year(df,ax=ax1)
    scatter_loa(df,ax=ax2)
    plt.show()
    diplay_listings(df)
    


# In[15]:


summary(
    listings(
        'Swan',
        max_year=1990,
    )
)


# In[16]:


summary(
    listings(
        'Arcona'
    )
)


# In[ ]:


#saving page cache file
save_obj(page_cache,cache_filename)


# In[ ]:


get_page('https://www.approvedboats.com/co-brokerage-boats-for-sale/all-Sail/?AdvancedKeywordSearch=x-yachts&max-price=500000&currency=EUR')


# In[ ]:





from dotenv import load_dotenv
load_dotenv()
import requests, os
WC_URL = os.getenv('WC_URL')
WC_KEY = os.getenv('WC_KEY')
WC_SECRET = os.getenv('WC_SECRET')
r = requests.get(f'{WC_URL}/wp-json/wc/v3/products/93625', params={'consumer_key': WC_KEY, 'consumer_secret': WC_SECRET})
p = r.json()
print('Categories:', [(c['id'], c['name'], c['slug']) for c in p.get('categories', [])])

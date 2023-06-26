from flask import Flask, render_template, send_file
import os
import json
import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd

app = Flask(__name__)

searched_products = []

class Product:
    def __init__(self,product_id, opinion_count=None, cons_count=None, pros_count=None, avg_rating=None, url=None, opinions=None):
        self.product_id = product_id
        self.opinion_count = opinion_count
        self.cons_count = cons_count
        self.pros_count = pros_count
        self.avg_rating = avg_rating
        self.url = url
        self.opinions = opinions

    
    def __str__(self):
        return f"Product(opinion_count={self.opinion_count}, cons_count={self.cons_count}, pros_count={self.pros_count}, avg_rating={self.avg_rating})"
        

class Opinion:
    def __init__(self, opinion_id=None, author=None, recommendation=None, score=None, confirmed=None, opinion_date=None, purchase_date=None, up_votes=None, down_votes=None, content=None, cons=None, pros=None):
        self.opinion_id = opinion_id
        self.author = author
        self.recommendation = recommendation
        self.score = score
        self.confirmed = confirmed
        self.opinion_date = opinion_date
        self.purchase_date = purchase_date
        self.up_votes = up_votes
        self.down_votes = down_votes
        self.content = content
        self.cons = cons
        self.pros = pros

    def get_pros_count(self):
        return len(self.pros)
    
    def get_cons_count(self):
        return len(self.cons)
    
    def get_score(self):
        return self.score

class ChartData:
    def __init__(self, recommend_count, not_recommend_count, stars) -> None:
        self.recommend = recommend_count
        self.not_recommend = not_recommend_count
        self.stars = stars



def write_list_of_dicts_to_excel(data_list, filename):
    df = pd.DataFrame(data_list)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    df.to_excel(writer, index=False)


def write_list_of_dicts_to_csv(data_list, filename):
    headers = list(data_list[0].keys())

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)

        writer.writeheader()

        for data in data_list:
            writer.writerow(data)

def count_params_for_product(opinions, url, product_id=None):

    pros_count = 0
    cons_count = 0
    rating = 0
    for opinion in opinions:
        pros_count += opinion.get_pros_count()
        cons_count += opinion.get_cons_count()
        rating += float(opinion.get_score()[0])
    if len(opinions) == 0:
        rating = 0
    else:
        rating = rating/len(opinions)
    product = Product(product_id, len(opinions), cons_count, pros_count, rating, url, opinions = opinions)
    searched_products.append(product)
    return product

def scrape_data(product_code):
    if product_code == None:
        return None
    selectors = {
        "opinion_id": (None, "data-entry-id"),
        "author": ("span.user-post__author-name",),
        "recommendation": ("span.user-post__author-recomendation > em",),
        "score": ("span.user-post__score-count",),
        "confirmed": ("div.review-pz",),
        "opinion_date": ("span.user-post__published > time:nth-child(1)","datetime"),
        "purchase_date": ("span.user-post__published > time:nth-child(2)","datetime"),
        "up_votes": ("span[id^='votes-yes']",),
        "down_votes": ("span[id^='votes-no']",),
        "content": ("div.user-post__text",),
        "cons": ("div.review-feature__col:has(> div.review-feature__title--negatives) > div.review-feature__item", None, True),
        "pros": ("div.review-feature__col:has(> div.review-feature__title--positives) > div.review-feature__item", None, True),
    }

    opinions_all = []
    url = f"https://www.ceneo.pl/{product_code}#tab=reviews"
    while url:
        response = requests.get(url)
        if response.status_code == requests.codes.ok:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review")
            opinions_for_product = []
            for opinion in opinions:
                single_opinion = {}
                for key, value in selectors.items():
                    single_opinion[key] = get_element(opinion, *value)
                opinion_obj = Opinion(
                    opinion_id=single_opinion['opinion_id'],
                    author=single_opinion['author'],
                    recommendation=single_opinion['recommendation'],
                    score=single_opinion['score'],
                    confirmed=single_opinion['confirmed'],
                    opinion_date=single_opinion['opinion_date'],
                    purchase_date=single_opinion['purchase_date'],
                    up_votes=single_opinion['up_votes'],
                    down_votes=single_opinion['down_votes'],
                    content=single_opinion['content'],
                    cons=single_opinion['cons'],
                    pros=single_opinion['pros']
                )
                opinions_for_product.append(opinion_obj)
                opinions_all.append(single_opinion)
            product = count_params_for_product(opinions_for_product, url, product_code)

            try:
                url = "https://www.ceneo.pl"+get_element(page_dom, "a.pagination__next", "href")
            except TypeError:
                url = None
            
        elif response.status_code == requests.codes.not_found:
            return None


    if not os.path.exists("./opinions/json"):
        os.mkdir("./opinions/json")
    with open(f"./opinions/json/{product_code}.json", "w", encoding="UTF-8") as jf:
        json.dump(opinions_all, jf, indent=4, ensure_ascii=False)
    
    if not os.path.exists("./opinions/xlsx"):
        os.mkdir("./opinions/xlsx")
    with open(f"./opinions/xlsx/{product_code}.xlsx", "w", encoding="UTF-8") as jf:
        write_list_of_dicts_to_excel(opinions_all, f"./opinions/xlsx/{product_code}.xlsx")

    if not os.path.exists("./opinions/csv"):
        os.mkdir("./opinions/csv")
    with open(f"./opinions/csv/{product_code}.csv", "w", encoding="UTF-8") as jf:
        write_list_of_dicts_to_csv(opinions_all, f"./opinions/csv/{product_code}.csv")

    return "Data scraped and saved successfully!", product

@app.route('/', methods=['GET'])
def load_page():
    return render_template('index.html')
    
@app.route('/extract', methods=['GET'])
def extract_opinions():
    return render_template('extract.html')

@app.route('/product/<product_code>', methods=['GET'])
def load_product_page(product_code):
    x = scrape_data(product_code)
    if x == None:
        return render_template('extract.html', error="Product not found")
    else:
        product = x[1] 
        return render_template('product-page.html', product=product, opinions=product.opinions)

@app.route('/products', methods=['GET'])
def load_products_page():
    return render_template('products.html', products=searched_products)

@app.route('/author', methods=['GET'])
def load_author_page():
    return render_template('author.html')

@app.route('/download/<type>/<filename>', methods=['GET'])
def download_file(type, filename):
    directory = 'opinions'

    file_path = os.path.join(directory, type, filename)

    if os.path.isfile(file_path):
        return send_file(file_path, as_attachment=True)
    return "nie znaleziono pliku"

@app.route('/charts/<product_id>', methods=['GET'])
def load_charts_page(product_id):
    for product in searched_products:
        if product.product_id == product_id:
            break
    count_recommend = 0
    count_not_recommend = 0
    stars = [0,0,0,0,0]
    for opinion in product.opinions:
        if opinion.recommendation == "Polecam":
            count_recommend += 1
        elif opinion.recommendation == "Nie polecam":
            count_not_recommend += 1
        stars[int(opinion.score[0])-1] += 1
    
    chart_data = ChartData(count_recommend, count_not_recommend, stars)

    return render_template('charts.html', chart_data=chart_data, product=product)



def get_element(ancestor, selector=None, attribute=None, return_list=False):
    try:
        if return_list:
            return [tag.get_text().strip() for tag in ancestor.select(selector)]
        if selector:
            if attribute:
                return ancestor.select_one(selector)[attribute].strip()
            return ancestor.select_one(selector).get_text().strip()
        return ancestor[attribute]
    except (AttributeError, TypeError):
        return None


#scrape_data("135886786")
#scrape_data("100001204")
#scrape_data("138536499")

if __name__ == '__main__':
    app.run()

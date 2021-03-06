import scrapy

class RecipesSpider(scrapy.Spider):
    name = "recipes"

    def __init__(self, pagestart='', pageend='', **kwargs):
        # Create search page URL's from page 1 to page N passed as parameter
        baseUrl = 'https://lifestyle.sapo.pt/pesquisar?pagina='
        self.start_urls = [baseUrl + str(i) + '&q=&filtro=receitas' for i in range(int(pagestart),int(pageend)+1)]
        
        super().__init__(**kwargs)

    def parse(self, response):
        # Extract recipes from search page
        allHref = response.css('article.recipe')

        # Prevent infinite recursion (recipe page also has the tag by which the URL's are discovered)
        if response.request.url.startswith('https://lifestyle.sapo.pt/sabores/receitas'):

            # Start making a new dicionary entry
            newRecipe = {}
            newRecipe['name'] = response.css('h1.recipe-title::text').extract_first()
            newRecipe['url'] = response.request.url

            # Assume recipe is not vegan (this will be updated later if it is)
            newRecipe['vegan'] = False

            # Get properties (dish type, speed, difficulty, ...) of the recipe
            properties = ['cuisine', 'dish', 'time', 'difficulty', 'cost', 'calories-level', 'servings']

            # These will be the keys in the firestore db
            pKeys = {'cuisine': 'gastronomia', 'dish': 'tipo', 'time': 'tempo', 
                    'difficulty': 'dificuldade', 'cost': 'custo', 
                    'calories-level': 'calorias', 'servings': 'porção'}
            
            for p in properties:
                # Get each property name-value pair (gastronomy: international, time: quick, ...)
                value = response.css('tr.'+p)

                # Some properties aren't available in all recipes (cost and calories)
                if value.css('td.name::text').extract_first() == None: continue

                # Some properties aren't a simple value but a graphical representation
                elif p == 'time' or p == "difficulty" or p == 'cost' or p == 'calories-level':
                    newRecipe[pKeys[p]] = value.css('div::attr(data-tip-text)').extract_first()

                # Simple text value
                elif p == 'servings':
                    newRecipe[pKeys[p]] = value.css('td.value::text').extract_first()
                
                # Some properties have a hyperlink (cuisine and dish)
                else:
                    newRecipe[pKeys[p]] = value.css('a::text').extract_first()

                    #Also check if it's a vegan recipe (if cuisine is 'Vegetariana' or dish is 'Vegetariano')
                    if (p == 'cuisine' and newRecipe[pKeys[p]] in 'Vegetariana') or (p == 'dish' and newRecipe[pKeys[p]] in 'Vegetariano'):
                        newRecipe['vegan'] = True

            # Create new dictionaries to hold ingredients and quantities (and counters, to serve as keys)
            newRecipeIngredients = {}
            newRecipeQuantities = {}
            iCounter=0
            qCounter=0

            # Get ingredients and their quantities
            ingredientTable = response.css('table.ingredients-table')
            for ingredients, quantities in zip(ingredientTable.css('td.ingredient-name::text'), ingredientTable.css('td.ingredient-quantity::text')):
                newRecipeIngredients[iCounter] = ingredients.extract()
                newRecipeQuantities[qCounter] = quantities.extract() + ' de ' + ingredients.extract()

                iCounter+=1
                qCounter+=1

            # Add ingredients and quantities to root dictionary
            newRecipe['ingredients'] = newRecipeIngredients
            newRecipe['quantidade'] = newRecipeQuantities

            # Create new dictionary to hold preparation paragraphs (and counter to serve as key)
            newRecipePrep = {}
            pCounter=0

            # Get each paragraph from preparation section
            preparation = response.css('section.recipe-preparation')
            for paragraph in preparation.css('p::text'):
                newRecipePrep[pCounter] = paragraph.extract()

                pCounter+=1

            # Add preparation to root dictionary
            newRecipe['preparação'] = newRecipePrep
            
            # Return the recipe dictionary
            yield newRecipe

        else:
            for href in allHref:
                # Get URL text (in format /sabores/<name> and prepend base URL to it)
                newUrl = href.css('a::attr(href)').extract_first()
                newUrl = 'https://lifestyle.sapo.pt' + newUrl

                # Recursively call this function with new URL
                yield scrapy.Request(newUrl, callback=self.parse)
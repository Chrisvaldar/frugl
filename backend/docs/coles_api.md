API Overview
The Coles Product API allows you to search for products by name, returning detailed information including, product name, brand, current price, size, and a URL to the product page. Suitable for retrieving a specific number of product entries per page with pagination support.

The Coles Product API provides a robust solution for querying Coles's extensive product catalog. Users can perform product searches using a simple query input and refine results based on page size and page number, enabling efficient data navigation and retrieval.

Features:
Product Search: Input a keyword to search across Coles’s product database.
Pagination: Control the volume of results with parameters for page size (1-20 entries per page) and page number, allowing for scalable data fetching.
Detailed Results: Each product entry in the search result includes:
Product Name: The full name of the product.
Product Brand: Brand association of the product.
Current Price: Latest price of the product as it appears in the store.
Product Size: The size or quantity of the product package.
URL: A direct link to the product’s page on the Coles website for further details.
Output Example:
Query: "Kraft Singles"
Total Results: 71 products found.
Total Pages: 8, indicating the search results span across eight pages.
Current Page: 1, showing results from the first page.
Results array with detailed product information, including, names, brands, prices, sizes, and URLs.
This API is perfect for developers building applications that require access to retail product data, providing all necessary information to feature Coles products comprehensively.

The Coles Product API allows you to search for products by name, returning detailed information including, product name, brand, current price, size, and a URL to the product page. Suitable for retrieving a specific number of product entries per page with pagination support. The Coles Product API provides a robust solution for querying Coles's extensive product catalog. Users can perform product searches using a simple query input and refine results based on page size and page number, enabling efficient data navigation and retrieval. #### Features: - **Product Search**: Input a keyword to search across Coles’s product database. - **Pagination**: Control the volume of results with parameters for page size (1-20 entries per page) and page number, allowing for scalable data fetching. - **Detailed Results**: Each product entry in the search result includes: - **Product Name**: The full name of the product. - **Product Brand**: Brand association of the product. - **Current Price**: Latest price of the product as it appears in the store. - **Product Size**: The size or quantity of the product package. - **URL**: A direct link to the product’s page on the Coles website for further details. #### Output Example: - **Query**: "Kraft Singles" - **Total Results**: 71 products found. - **Total Pages**: 8, indicating the search results span across eight pages. - **Current Page**: 1, showing results from the first page. - Results array with detailed product information, including, names, brands, prices, sizes, and URLs. This API is perfect for developers building applications that require access to retail product data, providing all necessary information to feature Coles products comprehensively.

# Coles RapidAPI

## Endpoints

### Price Changes
curl --request GET \
	--url 'https://coles-product-price-api.p.rapidapi.com/coles/price-changes/?date=2026-05-23&page=1&page_size=20' \
	--header 'Content-Type: application/json' \
	--header 'x-rapidapi-host: coles-product-price-api.p.rapidapi.com' \
	--header 'x-rapidapi-key: YOUR_KEY_HERE'

### Product Search
curl --request GET \
	--url 'https://coles-product-price-api.p.rapidapi.com/coles/product-search/?query=Full%20Cream%20Milk' \
	--header 'Content-Type: application/json' \
	--header 'x-rapidapi-host: coles-product-price-api.p.rapidapi.com' \
	--header 'x-rapidapi-key: YOUR_KEY_HERE'

Refer to @coles_sample_response.json for sample output of Product Search with Full Cream Milk as input
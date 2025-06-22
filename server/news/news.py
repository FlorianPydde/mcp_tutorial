"""
News MCP Server

A Model Context Protocol server that provides news information tools
using the NewsAPI.org service. Follows MCP SDK best practices
for server implementation, error handling, and transport configuration.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize logging with proper configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server with proper naming and configuration
mcp = FastMCP(
    name="news-service",
    dependencies=["httpx"],  # Explicit dependencies for deployment
)

# Constants
NEWS_API_BASE = "https://newsapi.org/v2"
USER_AGENT = "news-mcp-server/1.0"

# Get API key from environment
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


async def make_news_request(
    endpoint: str, params: Dict[str, Any] = None
) -> Dict[str, Any] | None:
    """Make a request to the News API with proper error handling and logging.

    Args:
        endpoint: The News API endpoint to request
        params: Optional query parameters

    Returns:
        JSON response data if successful, None if failed

    Raises:
        None - errors are logged and None is returned for graceful degradation
    """
    if not NEWS_API_KEY:
        logger.error("NEWS_API_KEY environment variable not set")
        return None

    url = f"{NEWS_API_BASE}/{endpoint}"
    headers = {
        "User-Agent": USER_AGENT,
        "X-API-Key": NEWS_API_KEY,
        "Accept": "application/json",
    }

    # Add default parameters
    if params is None:
        params = {}

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Making request to News API: {endpoint}")
            response = await client.get(
                url, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()

            data = response.json()

            # Check API response status
            if data.get("status") == "error":
                logger.error(f"News API error: {data.get('message', 'Unknown error')}")
                return None

            logger.info(f"Successfully retrieved data from {endpoint}")
            return data

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {endpoint}: {e}")
        if e.response.status_code == 401:
            logger.error(
                "Invalid API key. Please check NEWS_API_KEY environment variable"
            )
        elif e.response.status_code == 429:
            logger.error("Rate limit exceeded. Consider upgrading your News API plan")
        return None
    except httpx.TimeoutException:
        logger.error(f"Timeout requesting {endpoint}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error for {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error requesting {endpoint}: {e}")
        return None


def format_article(article: Dict[str, Any]) -> str:
    """Format an article into a readable string.

    Args:
        article: Article data from News API response

    Returns:
        Formatted article string with title, source, description, and URL
    """
    title = article.get("title", "No title available")
    source = article.get("source", {}).get("name", "Unknown Source")
    author = article.get("author", "Unknown Author")
    published_at = article.get("publishedAt", "Unknown Date")
    description = article.get("description", "No description available")
    url = article.get("url", "No URL available")

    # Format published date
    try:
        if published_at != "Unknown Date":
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            published_at = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass  # Keep original format if parsing fails

    return (
        f"Title: {title}\n"
        f"Source: {source}\n"
        f"Author: {author}\n"
        f"Published: {published_at}\n"
        f"Description: {description}\n"
        f"URL: {url}"
    )


@mcp.tool()
async def get_top_headlines(country: str = "us", category: Optional[str] = None) -> str:
    """Get top headlines from a specific country and optional category.

    Retrieves the latest top headlines from NewsAPI for the specified country.
    Provides comprehensive news information including title, source, description,
    and publication details.

    Args:
        country: Two-letter country code (e.g., 'us', 'gb', 'ca', 'au')
                Must be a valid ISO 3166-1 alpha-2 country code
        category: Optional news category filter. Valid categories:
                 'business', 'entertainment', 'general', 'health',
                 'science', 'sports', 'technology'

    Returns:
        Formatted string containing top headlines for the country/category,
        or an error message if the request fails

    Example:
        get_top_headlines("us", "technology") -> Returns tech headlines from US
    """
    # Validate country code format
    if not country or len(country) != 2:
        return "Error: Please provide a valid two-letter country code (e.g., 'us', 'gb', 'ca')"

    country = country.lower().strip()

    # Validate category if provided
    valid_categories = {
        "business",
        "entertainment",
        "general",
        "health",
        "science",
        "sports",
        "technology",
    }

    if category and category.lower() not in valid_categories:
        return (
            f"Error: Invalid category '{category}'. Valid categories: "
            f"{', '.join(sorted(valid_categories))}"
        )

    params = {
        "country": country,
        "pageSize": 10,  # Limit to top 10 headlines
    }

    if category:
        params["category"] = category.lower()

    logger.info(f"Fetching top headlines for country: {country}, category: {category}")

    data = await make_news_request("top-headlines", params)

    if not data:
        return f"Unable to fetch top headlines for country '{country}'. Please check your API key and try again."

    articles = data.get("articles", [])
    if not articles:
        filter_desc = f" in {category}" if category else ""
        return f"No top headlines found for {country.upper()}{filter_desc}."

    try:
        formatted_articles = [format_article(article) for article in articles]
        result = (
            f"Top Headlines for {country.upper()}"
            + (f" - {category.title()}" if category else "")
            + ":\n\n"
        )
        result += "\n" + "=" * 80 + "\n".join(formatted_articles)
        logger.info(f"Successfully formatted {len(articles)} headlines for {country}")
        return result
    except Exception as e:
        logger.error(f"Error formatting headlines for {country}: {e}")
        return f"Error processing headlines for {country}. Please try again."


@mcp.tool()
async def search_news(
    query: str, language: str = "en", sort_by: str = "publishedAt"
) -> str:
    """Search for news articles based on keywords.

    Searches through millions of articles from news sources and blogs
    using the NewsAPI everything endpoint. Provides flexible search
    with language and sorting options.

    Args:
        query: Keywords or phrases to search for in article titles and bodies
               Supports advanced search operators (AND, OR, NOT, quotes)
        language: Language code for articles (default: 'en' for English)
                 Supported: 'ar', 'de', 'en', 'es', 'fr', 'he', 'it', 'nl',
                 'no', 'pt', 'ru', 'sv', 'ud', 'zh'
        sort_by: Sort order for results. Options:
                'relevancy' - articles most relevant to query first
                'popularity' - articles from popular sources first
                'publishedAt' - newest articles first (default)

    Returns:
        Formatted string containing search results with article details,
        or an error message if the request fails

    Example:
        search_news("artificial intelligence", "en", "relevancy")
        -> Returns AI-related articles sorted by relevance
    """
    # Validate query
    if not query or len(query.strip()) < 2:
        return "Error: Please provide a search query with at least 2 characters"

    query = query.strip()

    # Validate language
    valid_languages = {
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "he",
        "it",
        "nl",
        "no",
        "pt",
        "ru",
        "sv",
        "ud",
        "zh",
    }

    if language.lower() not in valid_languages:
        return (
            f"Error: Invalid language '{language}'. Valid languages: "
            f"{', '.join(sorted(valid_languages))}"
        )

    # Validate sort_by
    valid_sort_options = {"relevancy", "popularity", "publishedAt"}

    if sort_by not in valid_sort_options:
        return (
            f"Error: Invalid sort option '{sort_by}'. Valid options: "
            f"{', '.join(sorted(valid_sort_options))}"
        )

    # Set date range to last 30 days (News API limitation for free tier)
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "language": language.lower(),
        "sortBy": sort_by,
        "from": from_date,
        "pageSize": 10,  # Limit to 10 results
    }

    logger.info(
        f"Searching news for query: '{query}', language: {language}, sort: {sort_by}"
    )

    data = await make_news_request("everything", params)

    if not data:
        return f"Unable to search news for query '{query}'. Please check your API key and try again."

    articles = data.get("articles", [])
    total_results = data.get("totalResults", 0)

    if not articles:
        return f"No news articles found for query '{query}'."

    try:
        formatted_articles = [format_article(article) for article in articles]
        result = f"News Search Results for '{query}' ({total_results:,} total results, showing top {len(articles)}):\n\n"
        result += "\n" + "=" * 80 + "\n".join(formatted_articles)
        logger.info(
            f"Successfully formatted {len(articles)} search results for '{query}'"
        )
        return result
    except Exception as e:
        logger.error(f"Error formatting search results for '{query}': {e}")
        return f"Error processing search results for '{query}'. Please try again."


@mcp.resource("news://service/info")
def get_service_info() -> str:
    """Provide information about the news service capabilities.

    Returns static information about what this MCP server can do.
    Resources are used for contextual data that LLMs can reference.
    """
    return """News MCP Server Information

This server provides news information tools using the NewsAPI.org service.

Available Tools:
- get_top_headlines(country, category): Get top headlines for a country/category
- search_news(query, language, sort_by): Search news articles by keywords

Supported Countries:
- US (us), United Kingdom (gb), Canada (ca), Australia (au)
- Germany (de), France (fr), Spain (es), Italy (it)
- Japan (jp), China (cn), India (in), Brazil (br)
- And many more ISO 3166-1 alpha-2 country codes

Supported Categories:
- business, entertainment, general, health
- science, sports, technology

Supported Languages:
- English (en), Spanish (es), French (fr), German (de)
- Chinese (zh), Japanese (ja), Arabic (ar), Russian (ru)
- And more (see ISO 639-1 language codes)

Data Source:
- NewsAPI.org - Over 80,000 news sources worldwide
- Real-time news updates
- Requires API key (free tier: 1,000 requests/day)

API Key Setup:
- Get free API key from https://newsapi.org
- Set NEWS_API_KEY environment variable
- Free tier limitations: 1,000 requests/day, 30-day article history
"""


if __name__ == "__main__":
    import sys

    import uvicorn

    # Support multiple transports following MCP SDK patterns
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"

    logger.info(f"Starting news MCP server with {transport} transport")

    if transport == "streamable-http":
        # Streamable HTTP transport (recommended for production)
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))  # Use PORT environment variable

        logger.info(f"Starting MCP news server (Streamable HTTP) on {host}:{port}")
        logger.info("MCP endpoint will be available at /mcp")

        # Use uvicorn with FastMCP app directly (production pattern)
        starlette_app = mcp.streamable_http_app()

        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Run with proper async context
        import asyncio

        asyncio.run(server.serve())

    else:
        # stdio transport for local/desktop integration
        logger.info("Starting MCP news server with stdio transport")
        logger.info("Server ready for stdio communication")
        mcp.run(transport="stdio")

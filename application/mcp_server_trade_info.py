import logging
import json
import sys
import trade_info
from typing import Dict, Optional, List
from mcp.server.fastmcp import FastMCP 

logging.basicConfig(
    level=logging.INFO,  # Default to INFO level
    format='%(filename)s:%(lineno)d | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp_server_trade_info")

try:
    mcp = FastMCP(
        name = "trade_info"
    )
    logger.info("MCP server initialized successfully")
except Exception as e:
        err_msg = f"Error: {str(e)}"
        logger.info(f"{err_msg}")

stocks = {}

######################################
# Time
######################################
@mcp.tool()
def retrieve_stock_trend(company_name: str = "네이버", period: int = 30) -> str:
    """
    Retrieve stock price trend. Returns the last ~period days of stock price history
    for the given company as a JSON string.
    company_name: company name to look up stock prices for
    period: number of days of stock price history to retrieve
    return: JSON string containing stock price trend data
    """
    logger.info(f"get_stock_trend --> company_name: {company_name}, period: {period}")

    result_dict = trade_info.get_stock_trend(company_name, period)

    stocks[f"{company_name}_{period}"] = result_dict

    return json.dumps(result_dict, ensure_ascii=False)

@mcp.tool()
def draw_stock_trend(company_name: str = "네이버", period: int = 30) -> Dict[str, List[str]]:
    """
    Draw a stock price trend chart. Renders a graph image of the given company's
    stock price history (use the same company_name and period as retrieve_stock_trend).
    company_name: company name to chart stock prices for
    period: number of days of stock price history to chart
    return: dictionary with a 'path' key containing a list of stock chart image file paths
    """
    logger.info(f"draw_stock_trend --> company_name: {company_name}, period: {period}")

    trend_dict = stocks.get(f"{company_name}_{period}")
    if trend_dict is None:
        logger.error(f"Trend not found for {company_name}_{period}")
        trend_dict = trade_info.get_stock_trend(company_name, period)
        stocks[f"{company_name}_{period}"] = trend_dict

    logger.info(f"trend_dict: {trend_dict}")

    return trade_info.draw_stock_trend(trend_dict)

if __name__ =="__main__":
    mcp.run(transport="stdio")



#!/usr/bin/env python3
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import argparse
import os
import pytz

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lista de estações conhecidas com seus códigos e nomes
KNOWN_STATIONS = {
    "1000840": "Ipiranga - Ribeirão dos Meninos",
    "1000839": "Cidade Universitária",
    "1000838": "Morumbi - USP",
    "1000837": "Vila Maria",
    "1000836": "Santana",
    "1000835": "Sé - Centro",
    "1000834": "Vila Prudente",
    "1000833": "Itaim Paulista",
    "1000832": "Jardim São Luís",
    "1000831": "Capela do Socorro",
    "1000830": "Parelheiros"
}

class CGESPScraper:
    def __init__(self):
        self.base_url = "https://www.cgesp.org/v3/estacoes-meteorologicas.jsp"
        
    def setup_driver(self):
        """Setup Chrome driver with headless options"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        return webdriver.Chrome(options=chrome_options)
    
    def get_station_url(self, station_code: str) -> str:
        """Get direct URL for specific station"""
        return f"https://www.cgesp.org/v3/estacao.jsp?POSTO={station_code}"
    
    def get_available_stations(self, driver) -> List[Dict[str, str]]:
        """Get list of available stations from dropdown"""
        try:
            station_dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "estacao"))
            )
            
            from selenium.webdriver.support.ui import Select
            select = Select(station_dropdown)
            stations = []
            
            for option in select.options:
                station_text = option.text.strip()
                station_value = option.get_attribute('value')
                if station_text and station_value:
                    # Extrair código da estação do value (assumindo formato: "1000840 - Ipiranga")
                    code_match = re.match(r'^(\d+)', station_value)
                    if code_match:
                        station_code = code_match.group(1)
                        stations.append({
                            'code': station_code,
                            'name': station_text,
                            'value': station_value
                        })
            
            return stations
        except Exception as e:
            logger.error(f"Error getting stations: {e}")
            return []
        
    def scrape_data(self, station_code: str) -> Dict[str, Any]:
        """Scrape weather data for specific station using direct URL"""
        driver = None
        try:
            driver = self.setup_driver()
            station_url = self.get_station_url(station_code)
            logger.info(f"Scraping data from URL: {station_url}")
            
            driver.get(station_url)
            
            # Wait for page to load
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract station name from the page
            station_name = self._extract_station_name(soup, station_code)
            
            # Extract data
            data = {
                'station_code': station_code,
                'station_name': station_name,
                'timestamp': datetime.now(pytz.timezone('America/Sao_Paulo')).isoformat(),
                'rain': self._extract_rain_data(soup),
                'temperature': self._extract_temperature_data(soup),
                'humidity': self._extract_humidity_data(soup),
                'wind': self._extract_wind_data(soup),
                'pressure': self._extract_pressure_data(soup),
                'history': self._extract_history_data(soup)
            }
            
            logger.info(f"Successfully scraped data for station {station_code} - {station_name}")
            return data
            
        except Exception as e:
            logger.error(f"Error scraping data for station {station_code}: {e}")
            return {}
        finally:
            if driver:
                driver.quit()
    
    def _extract_station_name(self, soup: BeautifulSoup, station_code: str) -> str:
        """Extract station name from the page"""
        try:
            # Look for station name in the page title or headers
            title = soup.find('title')
            if title and title.text:
                # Extrair nome da estação do título
                name_match = re.search(r'Estacao Meteorologica - (.*?) -', title.text)
                if name_match:
                    return name_match.group(1).strip()
            
            # Look for station name in h1 or h2 tags
            for header in soup.find_all(['h1', 'h2', 'h3']):
                if 'estacao' in header.text.lower() or 'meteorologica' in header.text.lower():
                    return header.text.strip()
            
            # Fallback: use known stations mapping
            return KNOWN_STATIONS.get(station_code, f"Estacao_{station_code}")
            
        except Exception:
            return KNOWN_STATIONS.get(station_code, f"Estacao_{station_code}")
    
    def _clean_text(self, text: str) -> str:
        """Clean text from encoding issues and extra spaces"""
        if not text:
            return ""
        # Fix common encoding issues
        text = text.replace('�', 'í').replace('�', 'á').replace('�', 'ã')
        text = text.replace('�', 'ó').replace('�', 'ê').replace('�', 'â')
        # Remove extra spaces and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _extract_value(self, text: str) -> float:
        """Extract numeric value from text"""
        try:
            # Remove non-numeric characters except decimal point and minus sign
            clean_text = re.sub(r'[^\d.-]', '', text)
            return float(clean_text) if clean_text else 0.0
        except ValueError:
            return 0.0
    
    def _extract_rain_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract rainfall data"""
        rain_data = {}
        try:
            # Look for rain section
            rain_section = soup.find(string=re.compile("Chuva.*Por Período", re.IGNORECASE))
            if not rain_section:
                # Try alternative patterns
                rain_section = soup.find(string=re.compile("Precipitação", re.IGNORECASE))
            
            if rain_section:
                rain_container = rain_section.find_parent()
                rain_text = rain_container.get_text() if rain_container else ""
                
                # Extract values using regex
                current_match = re.search(r"Per\. Atual:\s*([\d.]+)\s*mm", rain_text)
                previous_match = re.search(r"Per\. Anterior:\s*([\d.]+)\s*mm", rain_text)
                reset_match = re.search(r"Zeramento:\s*(\d{2}:\d{2}:\d{2})", rain_text)
                
                rain_data = {
                    'current': self._extract_value(current_match.group(1)) if current_match else 0.0,
                    'previous': self._extract_value(previous_match.group(1)) if previous_match else 0.0,
                    'reset_time': reset_match.group(1) if reset_match else "00:00:00"
                }
        except Exception as e:
            logger.error(f"Error extracting rain data: {e}")
            rain_data = {'current': 0.0, 'previous': 0.0, 'reset_time': "00:00:00"}
        
        return rain_data
    
    def _extract_temperature_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract temperature data"""
        temp_data = {}
        try:
            # Look for temperature section
            temp_section = soup.find(string=re.compile("Temperatura", re.IGNORECASE))
            if temp_section:
                temp_container = temp_section.find_parent()
                temp_text = temp_container.get_text() if temp_container else ""
                
                # Extract values using regex
                current_match = re.search(r"Atual:\s*([\d.]+)\s*°?C", temp_text, re.IGNORECASE)
                max_match = re.search(r"Máxima:\s*([\d.]+)\s*°?C", temp_text, re.IGNORECASE)
                min_match = re.search(r"Mínima:\s*([\d.]+)\s*°?C", temp_text, re.IGNORECASE)
                
                temp_data = {
                    'current': self._extract_value(current_match.group(1)) if current_match else 0.0,
                    'max': self._extract_value(max_match.group(1)) if max_match else 0.0,
                    'min': self._extract_value(min_match.group(1)) if min_match else 0.0
                }
        except Exception as e:
            logger.error(f"Error extracting temperature data: {e}")
            temp_data = {'current': 0.0, 'max': 0.0, 'min': 0.0}
        
        return temp_data
    
    def _extract_humidity_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract humidity data"""
        humidity_data = {}
        try:
            # Look for humidity section
            humidity_section = soup.find(string=re.compile("Umidade", re.IGNORECASE))
            if humidity_section:
                humidity_container = humidity_section.find_parent()
                humidity_text = humidity_container.get_text() if humidity_container else ""
                
                # Extract values using regex
                current_match = re.search(r"Atual:\s*([\d.]+)\s*%", humidity_text, re.IGNORECASE)
                max_match = re.search(r"Máxima:\s*([\d.]+)\s*%", humidity_text, re.IGNORECASE)
                min_match = re.search(r"Mínima:\s*([\d.]+)\s*%", humidity_text, re.IGNORECASE)
                
                humidity_data = {
                    'current': self._extract_value(current_match.group(1)) if current_match else 0.0,
                    'max': self._extract_value(max_match.group(1)) if max_match else 0.0,
                    'min': self._extract_value(min_match.group(1)) if min_match else 0.0
                }
        except Exception as e:
            logger.error(f"Error extracting humidity data: {e}")
            humidity_data = {'current': 0.0, 'max': 0.0, 'min': 0.0}
        
        return humidity_data
    
    def _extract_wind_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract wind data"""
        wind_data = {}
        try:
            # Look for wind section
            wind_section = soup.find(string=re.compile("Vento", re.IGNORECASE))
            if wind_section:
                wind_container = wind_section.find_parent()
                wind_text = wind_container.get_text() if wind_container else ""
                
                # Extract values using regex
                speed_match = re.search(r"Velocidade:\s*([\d.]+)\s*km/h", wind_text, re.IGNORECASE)
                gust_match = re.search(r"Rajada:\s*([\d.]+)\s*km/h", wind_text, re.IGNORECASE)
                
                wind_data = {
                    'speed': self._extract_value(speed_match.group(1)) if speed_match else 0.0,
                    'gust': self._extract_value(gust_match.group(1)) if gust_match else 0.0
                }
        except Exception as e:
            logger.error(f"Error extracting wind data: {e}")
            wind_data = {'speed': 0.0, 'gust': 0.0}
        
        return wind_data
    
    def _extract_pressure_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract pressure data"""
        pressure_data = {}
        try:
            # Look for pressure section
            pressure_section = soup.find(string=re.compile("Pressão", re.IGNORECASE))
            if pressure_section:
                pressure_container = pressure_section.find_parent()
                pressure_text = pressure_container.get_text() if pressure_container else ""
                
                # Extract values using regex
                current_match = re.search(r"Atual:\s*([\d.]+)\s*hPa", pressure_text, re.IGNORECASE)
                max_match = re.search(r"Máxima:\s*([\d.]+)\s*hPa", pressure_text, re.IGNORECASE)
                min_match = re.search(r"Mínima:\s*([\d.]+)\s*hPa", pressure_text, re.IGNORECASE)
                
                pressure_data = {
                    'current': self._extract_value(current_match.group(1)) if current_match else 0.0,
                    'max': self._extract_value(max_match.group(1)) if max_match else 0.0,
                    'min': self._extract_value(min_match.group(1)) if min_match else 0.0
                }
        except Exception as e:
            logger.error(f"Error extracting pressure data: {e}")
            pressure_data = {'current': 0.0, 'max': 0.0, 'min': 0.0}
        
        return pressure_data
    
    def _extract_history_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract historical data from the table"""
        history_data = []
        try:
            # Find the historical data table
            tables = soup.find_all('table')
            for table in tables:
                # Look for table with historical data headers
                headers = table.find_all('th')
                if len(headers) >= 7:  # Should have at least 7 columns based on the screenshot
                    # Extract header names
                    header_texts = [self._clean_text(header.get_text()) for header in headers]
                    
                    # Check if this is the history table
                    if any('Data' in text for text in header_texts) and any('Chuva' in text for text in header_texts):
                        # Extract rows
                        rows = table.find_all('tr')[1:]  # Skip header row
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) >= 7:
                                history_entry = {
                                    'date': self._clean_text(cols[0].get_text()),
                                    'rain': self._extract_value(cols[1].get_text()),
                                    'wind_speed': self._extract_value(cols[2].get_text()),
                                    'wind_direction': self._extract_value(cols[3].get_text()),
                                    'temperature': self._extract_value(cols[4].get_text()),
                                    'humidity': self._extract_value(cols[5].get_text()),
                                    'pressure': self._extract_value(cols[6].get_text())
                                }
                                history_data.append(history_entry)
                        break
        except Exception as e:
            logger.error(f"Error extracting history data: {e}")
        
        return history_data

class HomeAssistantIntegration:
    def __init__(self, ha_url: str, ha_token: str):
        self.ha_url = ha_url.rstrip('/')
        self.ha_token = ha_token
        self.headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json"
        }
        
    def send_sensor_data(self, entity_id: str, state: Any, attributes: Dict[str, Any]):
        """Send sensor data to Home Assistant"""
        url = f"{self.ha_url}/api/states/{entity_id}"
        
        data = {
            "state": state,
            "attributes": attributes
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            logger.info(f"Successfully updated {entity_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating {entity_id}: {e}")
            return False

async def main():
    parser = argparse.ArgumentParser(description='CGESP Weather Scraper')
    parser.add_argument('--station_code', default='1000840', help='Station code to monitor (e.g., 1000840 for Ipiranga)')
    parser.add_argument('--scan_interval', type=int, default=3600, help='Scan interval in seconds')
    parser.add_argument('--ha_url', default='http://supervisor/core', help='Home Assistant URL')
    parser.add_argument('--ha_token', required=True, help='Home Assistant API token')
    
    args = parser.parse_args()
    
    scraper = CGESPScraper()
    ha_integration = HomeAssistantIntegration(args.ha_url, args.ha_token)
    
    try:
        while True:
            start_time = time.time()
            logger.info(f"Starting data scrape for station code: {args.station_code}")
            
            # Scrape data
            data = scraper.scrape_data(args.station_code)
            
            if data:
                logger.info(f"Successfully scraped data from {data['station_code']} - {data['station_name']}")
                
                # Create slug for entity IDs
                station_slug = data['station_code']
                
                # Temperature sensor (will be stored in HA history)
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_temperature",
                    data['temperature'].get('current', 0),
                    {
                        "friendly_name": f"CGESP {data['station_name']} Temperature",
                        "unit_of_measurement": "°C",
                        "device_class": "temperature",
                        "state_class": "measurement",
                        "max_today": data['temperature'].get('max', 0),
                        "min_today": data['temperature'].get('min', 0),
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp']
                    }
                )
                
                # Humidity sensor (will be stored in HA history)
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_humidity",
                    data['humidity'].get('current', 0),
                    {
                        "friendly_name": f"CGESP {data['station_name']} Humidity",
                        "unit_of_measurement": "%",
                        "device_class": "humidity",
                        "state_class": "measurement",
                        "max_today": data['humidity'].get('max', 0),
                        "min_today": data['humidity'].get('min', 0),
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp']
                    }
                )
                
                # Rain sensor (will be stored in HA history)
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_rain",
                    data['rain'].get('current', 0),
                    {
                        "friendly_name": f"CGESP {data['station_name']} Rain",
                        "unit_of_measurement": "mm",
                        "device_class": "precipitation",
                        "state_class": "total_increasing",
                        "previous_period": data['rain'].get('previous', 0),
                        "reset_time": data['rain'].get('reset_time', '00:00:00'),
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp']
                    }
                )
                
                # Wind speed sensor (will be stored in HA history)
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_wind_speed",
                    data['wind'].get('speed', 0),
                    {
                        "friendly_name": f"CGESP {data['station_name']} Wind Speed",
                        "unit_of_measurement": "km/h",
                        "device_class": "wind_speed",
                        "state_class": "measurement",
                        "gust_speed": data['wind'].get('gust', 0),
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp']
                    }
                )
                
                # Pressure sensor (will be stored in HA history)
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_pressure",
                    data['pressure'].get('current', 0),
                    {
                        "friendly_name": f"CGESP {data['station_name']} Pressure",
                        "unit_of_measurement": "hPa",
                        "device_class": "pressure",
                        "state_class": "measurement",
                        "max_today": data['pressure'].get('max', 0),
                        "min_today": data['pressure'].get('min', 0),
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp']
                    }
                )
                
                # Also send the complete data as a single sensor
                ha_integration.send_sensor_data(
                    f"sensor.cgesp_{station_slug}_complete",
                    "Online",
                    {
                        "friendly_name": f"CGESP {data['station_name']} Complete Data",
                        "station_name": data['station_name'],
                        "station_code": data['station_code'],
                        "timestamp": data['timestamp'],
                        "rain": data['rain'],
                        "temperature": data['temperature'],
                        "humidity": data['humidity'],
                        "wind": data['wind'],
                        "pressure": data['pressure'],
                        "history": data['history']
                    }
                )
            else:
                logger.error("Failed to scrape data")
                
            # Calculate remaining time and wait for next scan
            elapsed_time = time.time() - start_time
            sleep_time = max(0, args.scan_interval - elapsed_time)
            
            logger.info(f"Scrape completed in {elapsed_time:.2f} seconds. Waiting {sleep_time:.2f} seconds until next scan")
            await asyncio.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
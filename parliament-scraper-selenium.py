from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import re
from typing import Dict, List
import time
import os
import json
import csv
from urllib.parse import urljoin
import argparse

class ParliamentScraper:
    def __init__(self, base_url: str = "http://www.cdep.ro", use_cache: bool = False):
        """
        Initialize the scraper
        
        Args:
            base_url (str): Base URL for the parliament website
            use_cache (bool): If True, use already downloaded files instead of downloading again
        """
        self.base_url = base_url
        self.use_cache = use_cache
        
        # Create directory for storing pages
        self.data_dir = "parliament_data"
        self.deputies_dir = os.path.join(self.data_dir, "deputies")
        os.makedirs(self.deputies_dir, exist_ok=True)
        
        # Only initialize Selenium if we're not using cache
        if not use_cache:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            self.driver = webdriver.Chrome(options=options)
            self.driver.implicitly_wait(10)

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

    def extract_deputies_from_file(self, file_path: str) -> List[Dict]:
        """
        Extract deputies information from the local HTML file using regex and BeautifulSoup
        """
        try:
            with open(file_path, "r", encoding="ISO-8859-1") as file:
                html_content = file.read()

            soup = BeautifulSoup(html_content, 'html.parser')
            deputies = []
            
            # Find all tables and try to identify the correct one
            tables = soup.find_all('table')
            print(f"\nFound {len(tables)} tables")
            
            target_table = None
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) > 1:  # Need at least header and one data row
                    first_row = rows[1]  # Check first data row
                    cells = first_row.find_all('td')
                    if len(cells) >= 4:  # We need at least 4 columns
                        # Check if second cell contains a link with 'idm' in it
                        link = cells[1].find('a')
                        if link and 'idm=' in link.get('href', ''):
                            target_table = table
                            print("Found deputies table!")
                            break
            
            if not target_table:
                print("Could not find deputies table")
                return []
                
            # Process each row
            for row in target_table.find_all('tr')[1:]:  # Skip header row
                cols = row.find_all('td')
                if len(cols) >= 4:  # We need at least 4 columns
                    # Extract deputy info from link
                    link = cols[1].find('a')
                    if link:
                        href = link['href']
                        # Print for debugging
                        print(f"\nProcessing link: {href}")
                        
                        match = re.search(r'idm=(\d+)', href)
                        if match:
                            deputy_id = match.group(1)
                            name = link.text.strip()
                            # Extract parliamentary group
                            group = cols[3].text.strip()
                            
                            deputy_info = {
                                'name': name,
                                'url': f"https://cdep.ro/pls/parlam/structura2015.mp?idm={deputy_id}",
                                'id': deputy_id,
                                'group': group
                            }
                            print(f"Found deputy: {name} ({group})")
                            deputies.append(deputy_info)

            print(f"\nFound {len(deputies)} deputies")
            
            # Save deputies info to JSON for reference
            with open(os.path.join(self.data_dir, 'deputies_info.json'), 'w', encoding='utf-8') as f:
                json.dump(deputies, f, ensure_ascii=False, indent=2)
                
            return deputies

        except Exception as e:
            print(f"Error extracting deputies from file: {e}")
            import traceback
            print(traceback.format_exc())
            return []

            print(f"Found {len(deputies)} deputies")
            
            # Save deputies info to JSON for reference
            with open(os.path.join(self.data_dir, 'deputies_info.json'), 'w', encoding='utf-8') as f:
                json.dump(deputies, f, ensure_ascii=False, indent=2)

            return deputies

        except Exception as e:
            print(f"Error extracting deputies from file: {e}")
            return []

    def save_page(self, filepath: str):
        """
        Save current page source to file
        """
        try:
            content = self.driver.page_source
            # Try different encodings
            for encoding in ['utf-8', 'iso-8859-1', 'iso-8859-2']:
                try:
                    with open(filepath, 'w', encoding=encoding) as f:
                        f.write(content)
                    print(f"Successfully saved page with {encoding} encoding")
                    break
                except UnicodeEncodeError:
                    continue
        except Exception as e:
            print(f"Error saving page {filepath}: {e}")

    def download_deputy_pages(self, deputies: List[Dict]):
        """
        Download individual deputy pages using Selenium
        """
        if self.use_cache:
            print("\nUsing cached deputy pages...")
            for deputy in deputies:
                filename = f"deputy_{deputy['id']}_{deputy['name'].replace(' ', '_')}.html"
                filepath = os.path.join(self.deputies_dir, filename)
                if os.path.exists(filepath):
                    deputy['local_file'] = filepath
                else:
                    print(f"Warning: Cache file not found for {deputy['name']}")
            return

        print("\nDownloading individual deputy pages...")
        for i, deputy in enumerate(deputies, 1):
            filename = f"deputy_{deputy['id']}_{deputy['name'].replace(' ', '_')}.html"
            filepath = os.path.join(self.deputies_dir, filename)
            
            print(f"Downloading {i}/{len(deputies)}: {deputy['name']}")
            
            try:
                self.driver.get(deputy['url'])
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "boxDep"))
                )
                self.save_page(filepath)
                deputy['local_file'] = filepath
                
            except TimeoutException:
                print(f"Timeout waiting for deputy page to load: {deputy['name']}")
            except Exception as e:
                print(f"Error downloading deputy page: {deputy['name']}, Error: {e}")
            
            time.sleep(1)

    def parse_deputy_committees(self, filepath: str) -> List[Dict]:
        """
        Parse committees from a deputy's downloaded page
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            committees = []
            
            # Find committee section
            committee_div = None
            for div in soup.find_all('div', class_='boxDep'):
                h3 = div.find('h3')
                if h3 and 'Comisii permanente' in h3.text:
                    committee_div = div
                    break
            
            if not committee_div:
                return []
            
            p_tag = committee_div.find('p')
            if not p_tag:
                return []
                
            # Get all text content including NavigableStrings between links
            for element in p_tag.contents:
                if element.name == 'a':
                    committee_info = {
                        'name': element.text.strip(),
                        'url': urljoin(self.base_url, element['href'])
                    }
                    committees.append(committee_info)
                elif isinstance(element, str):
                    text = element.strip(' -\n\r\t')
                    if text and committees:
                        committees[-1]['role'] = text
            
            return committees
            
        except Exception as e:
            print(f"Error parsing deputy page {filepath}")
            print(f"Error details: {str(e)}")
            return []

    def process_all(self, deputies_list_file: str = 'lista_deputati_chrome.html'):
        """
        Main process: Extract deputies from file, download their pages and create CSV
        """
        try:
            deputies = self.extract_deputies_from_file(deputies_list_file)
            if not deputies:
                print("No deputies found. Exiting.")
                return

            self.download_deputy_pages(deputies)

            with open('deputies_committees.csv', 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Deputy Name', 'Deputy URL', 'Deputy ID', 'Parliamentary Group', 'Committee Name', 'Committee URL', 'Role'])
                
                for deputy in deputies:
                    if 'local_file' not in deputy:
                        continue
                        
                    committees = self.parse_deputy_committees(deputy['local_file'])
                    
                    if not committees:
                        writer.writerow([
                            deputy['name'],
                            deputy['url'],
                            deputy['id'],
                            '',
                            '',
                            ''
                        ])
                    else:
                        for committee in committees:
                            writer.writerow([
                                deputy['name'],
                                deputy['url'],
                                deputy['id'],
                                deputy['group'],
                                committee['name'],
                                committee['url'],
                                committee.get('role', '')
                            ])
        except Exception as e:
            print(f"Error parsing deputy page {filepath}")
            print(f"Error details: {str(e)}")
            return []

        print("\nProcess completed!")
        print(f"- Raw data saved in: {self.data_dir}")
        print("- Final CSV saved as: deputies_committees.csv")

def main():
    parser = argparse.ArgumentParser(description='Scrape parliament deputies and their committees')
    parser.add_argument('--use-cache', action='store_true', 
                      help='Use already downloaded pages instead of downloading again')
    args = parser.parse_args()

    scraper = ParliamentScraper(use_cache=args.use_cache)
    scraper.process_all()

if __name__ == "__main__":
    main()

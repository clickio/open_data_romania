from bs4 import BeautifulSoup
import requests
import csv
import re
import os
import time
import json
from urllib.parse import urljoin

class SenatorsScraper:
    def __init__(self, base_url: str = "https://www.senat.ro", use_cache: bool = False):
        """
        Initialize the scraper
        
        Args:
            base_url (str): Base URL for the senate website
            use_cache (bool): If True, use already downloaded files instead of downloading again
        """
        self.base_url = base_url
        self.use_cache = use_cache
        
        # Create directories for storing pages
        self.data_dir = "senate_data"
        self.senators_dir = os.path.join(self.data_dir, "senators")
        os.makedirs(self.senators_dir, exist_ok=True)
        
        # Setup session for downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fix_romanian_chars(self, text):
        """Fix Romanian characters in text"""
        if not isinstance(text, str):
            return text
            
        replacements = {
            'º': 'ș',
            'þ': 'ț',
            'Þ': 'Ț',
            'ª': 'Ș'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def extract_senators_from_file(self, file_path: str) -> list:
        """Extract basic senator information from the main list page"""
        with open(file_path, "r", encoding="ISO-8859-1") as file:
            html_content = file.read()

        soup = BeautifulSoup(html_content, 'html.parser')
        senators = []

        cards = soup.find_all('div', class_='new-card-without-pics')
        print(f"Found {len(cards)} senator cards")

        for card in cards:
            try:
                link = card.find('a')
                if not link:
                    continue

                name = link.text.strip()
                href = link.get('href', '')
                senator_id = re.search(r'ParlamentarID=([^&]+)', href).group(1)

                text_lines = [line.strip() for line in card.get_text().split('\n') if line.strip()]

                birth_date = ""
                constituency = ""
                group = ""

                for line in text_lines:
                    if "Data nasterii:" in line:
                        birth_date = line.replace("Data nasterii:", "").strip()
                    elif "Circumscripţia electorală" in line:
                        constituency = line.strip()
                    elif "Grupul parlamentar" in line:
                        group = line.strip()

                senator_info = {
                    'id': senator_id,
                    'name': self.fix_romanian_chars(name),
                    'birth_date': birth_date,
                    'constituency': self.fix_romanian_chars(constituency),
                    'group': self.fix_romanian_chars(group),
                    'url': f"{self.base_url}/FisaSenator.aspx?ParlamentarID={senator_id}"
                }
                senators.append(senator_info)
                print(f"Processed: {name}")

            except Exception as e:
                print(f"Error processing card: {e}")
                continue

        # Save senators info to JSON for reference
        with open(os.path.join(self.data_dir, 'senators_info.json'), 'w', encoding='utf-8') as f:
            json.dump(senators, f, ensure_ascii=False, indent=2)

        return senators

    def download_senator_pages(self, senators: list):
        """Download individual senator pages"""
        print("\nDownloading individual senator pages...")
        
        for i, senator in enumerate(senators, 1):
            filename = f"senator_{senator['id']}.html"
            filepath = os.path.join(self.senators_dir, filename)
            
            if self.use_cache and os.path.exists(filepath):
                print(f"Using cached file for {senator['name']}")
                senator['local_file'] = filepath
                continue
                
            print(f"Downloading {i}/{len(senators)}: {senator['name']}")
            
            try:
                response = self.session.get(senator['url'])
                response.raise_for_status()
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                senator['local_file'] = filepath
                time.sleep(1)  # Be nice to the server
                
            except Exception as e:
                print(f"Error downloading senator page: {senator['name']}, Error: {e}")

    def parse_senator_committees(self, filepath: str) -> list:
        """Parse committees from a senator's downloaded page"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            committees = []
            
            # Find committees section
            h5 = soup.find('h5', string='Comisii permanente:')
            if not h5:
                return []
                
            # Get all links after the h5 heading until the next heading
            current = h5.find_next()
            while current and current.name != 'h5':
                if current.name == 'a':
                    committee_info = {
                        'name': self.fix_romanian_chars(current.text.strip()),
                        'url': urljoin(self.base_url, current['href'])
                    }
                    committees.append(committee_info)
                current = current.find_next()
            
            return committees
            
        except Exception as e:
            print(f"Error parsing senator page {filepath}: {e}")
            return []

    def process_all(self, senators_list_file: str = 'senatori.html'):
        """Main process: Extract senators from file, download their pages and create CSV"""
        try:
            # Step 1: Extract senators from local file
            senators = self.extract_senators_from_file(senators_list_file)
            if not senators:
                print("No senators found. Exiting.")
                return

            # Step 2: Download individual senator pages
            self.download_senator_pages(senators)

            # Step 3: Process all downloaded pages and create CSV
            with open('senators_committees.csv', 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Senator Name', 'Senator URL', 'Senator ID', 'Birth Date', 'Constituency', 
                               'Parliamentary Group', 'Committee Name', 'Committee URL'])
                
                for senator in senators:
                    if 'local_file' not in senator:
                        continue
                        
                    committees = self.parse_senator_committees(senator['local_file'])
                    
                    if not committees:
                        writer.writerow([
                            senator['name'],
                            senator['url'],
                            senator['id'],
                            senator['birth_date'],
                            senator['constituency'],
                            senator['group'],
                            '',
                            ''
                        ])
                    else:
                        for committee in committees:
                            writer.writerow([
                                senator['name'],
                                senator['url'],
                                senator['id'],
                                senator['birth_date'],
                                senator['constituency'],
                                senator['group'],
                                committee['name'],
                                committee['url']
                            ])
        except Exception as e:
            print(f"Error parsing some senator page")
            return []
        
        print("\nProcess completed!")
        print(f"- Raw data saved in: {self.data_dir}")
        print("- Final CSV saved as: senators_committees.csv")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape senate data and committees')
    parser.add_argument('--use-cache', action='store_true', 
                      help='Use already downloaded pages instead of downloading again')
    args = parser.parse_args()

    scraper = SenatorsScraper(use_cache=args.use_cache)
    scraper.process_all()

if __name__ == "__main__":
    main()
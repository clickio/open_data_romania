from bs4 import BeautifulSoup
import csv
import re

def extract_deputies(file_path="lista_deputati_chrome.html"):
    # Read the file
    with open(file_path, "r", encoding="ISO-8859-1") as file:
        html_content = file.read()

    # Initialize deputies list
    deputies = []

    # Use regex to extract IDs and names
    pattern = r'<a href="https://cdep.ro/pls/parlam/structura2015\.mp\?idm=(\d+).*?">\s*(.*?)\s*</a>'
    matches = re.findall(pattern, html_content)

    # Create BeautifulSoup object for full row data
    soup = BeautifulSoup(html_content, 'html.parser')
    rows = soup.find_all('tr')

    # Process each row to get all information
    for row in rows[1:]:  # Skip header
        cells = row.find_all('td')
        if len(cells) >= 4:
            link = cells[1].find('a')
            if link and 'idm=' in link.get('href', ''):
                deputy_id = re.search(r'idm=(\d+)', link['href']).group(1)
                name = link.text.strip()
                constituency = cells[2].text.strip()
                group = cells[3].text.strip()
                
                deputies.append({
                    'id': deputy_id,
                    'name': name,
                    'constituency': constituency,
                    'group': group,
                    'url': f"https://cdep.ro/pls/parlam/structura2015.mp?idm={deputy_id}"
                })

    # Write to CSV
    with open('deputies_basic.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Constituency', 'Parliamentary Group', 'URL'])
        
        for deputy in deputies:
            writer.writerow([
                deputy['id'],
                deputy['name'],
                deputy['constituency'],
                deputy['group'],
                deputy['url']
            ])

    print(f"Extracted {len(deputies)} deputies to deputies_basic.csv")

if __name__ == "__main__":
    extract_deputies()

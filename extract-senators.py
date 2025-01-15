from bs4 import BeautifulSoup
import csv
import re

def fix_romanian_chars(text):
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

def extract_senators(file_path="senatori.html"):
    # Read the file
    with open(file_path, "r", encoding="ISO-8859-1") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    senators = []

    # Find all senator cards
    cards = soup.find_all('div', class_='new-card-without-pics')
    print(f"Found {len(cards)} senator cards")

    for card in cards:
        try:
            # Extract senator info
            link = card.find('a')
            if not link:
                continue

            # Get name and ID
            name = link.text.strip()
            href = link.get('href', '')
            senator_id = re.search(r'ParlamentarID=([^&]+)', href).group(1)

            # Get the text content and split into lines
            text_lines = [line.strip() for line in card.get_text().split('\n') if line.strip()]

            # Extract other information using patterns
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
                'name': fix_romanian_chars(name),
                'birth_date': birth_date,
                'constituency': fix_romanian_chars(constituency),
                'group': fix_romanian_chars(group),
                'url': f"https://www.senat.ro/FisaSenator.aspx?ParlamentarID={senator_id}"
            }
            senators.append(senator_info)
            print(f"Processed: {name}")

        except Exception as e:
            print(f"Error processing card: {e}")
            continue

    # Write to CSV
    with open('senators_basic.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Birth Date', 'Constituency', 'Parliamentary Group', 'URL'])
        
        for senator in senators:
            writer.writerow([
                senator['id'],
                senator['name'],
                senator['birth_date'],
                senator['constituency'],
                senator['group'],
                senator['url']
            ])

    print(f"\nExtracted {len(senators)} senators to senators_basic.csv")

    # Print some basic statistics
    print("\nParliamentary Groups distribution:")
    groups = {}
    for senator in senators:
        group = senator['group']
        groups[group] = groups.get(group, 0) + 1
    
    for group, count in sorted(groups.items()):
        print(f"{group}: {count}")

if __name__ == "__main__":
    extract_senators()
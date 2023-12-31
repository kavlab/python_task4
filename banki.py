import requests
from bs4 import BeautifulSoup
import pandas as pd

# root URL
URL = 'https://www.banki.ru/banks/ratings/'

def get_page(url: str) -> BeautifulSoup:
    r"""Send a GET request to URL and return BeautifulSoup
    """
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return BeautifulSoup(response.text, 'html.parser')
    else:
        raise ValueError(response)

def clear_text(text: str) -> str:
    r"""Remove spaces and line breaks
    """
    lines = []
    for line in text.splitlines():
        if len(line.strip()) > 0:
            while '  ' in line:
                line = line.replace('  ', ' ')
            lines.append(line.strip())
    return ', '.join(lines)

def parse_table(page: BeautifulSoup) -> pd.DataFrame:
    r"""Parse page (BeautifulSoup) and return DataFrame
    """
    # finding main table
    table = page.find('table', {'class': 'standard-table standard-table--row-highlight margin-bottom-small margin-top-x-small'})

    # parsing header of the table
    thead = table.find('thead')
    # list with the captions for creating DataFrame
    captions = []
    # prefix for period columns
    period_caption = ''
    # prefix for change columns
    change_text = ''
    for th in thead.find_all('th', {'class': 'table-title'}):

        select = th.find('select')
        if select is None:

            cleared_text = clear_text(th.text)
            if 'показатель' in cleared_text:
                # set prefix for period columns
                period_caption = cleared_text.replace(',,', ',')
            elif 'изменение' in cleared_text:
                # set prefix for change columns
                change_text = cleared_text
            else:
                if change_text != '':
                    cleared_text = f'{change_text}, {cleared_text}'
                captions.append(cleared_text)
            
        else:
            option = select.find('option', {'selected': 'selected'})
            if option is not None:
                captions.append(f'{period_caption}, {clear_text(option.text)}')
    
    # create DataFrame with columns
    df = pd.DataFrame(columns=captions)

    # parsing body of the table
    tbody = table.find('tbody')

    cur_row = 1
    # rows loop
    for tr in tbody.find_all('tr'):

        row = []
        column_index = 1
        # columns loop
        for td in tr.find_all('td'):

            cleared_text = clear_text(td.text)

            if column_index in [3, 4, 5]:

                # numeric columns, remove ' ', '+', '−' and trying to convert to int
                cleared_text = cleared_text \
                    .replace(' ', '').replace('+', '').replace('−', '-')

                # check sign
                if cleared_text[0] == '-':
                    sign = -1
                    cleared_text = cleared_text[1:]
                else:
                    sign = 1
                
                # convert
                if cleared_text.isnumeric():
                    value = sign * int(cleared_text)
                else:
                    value = cleared_text
                
            elif column_index == 6:

                # percent column, remove ' ', '+', '−', ',', '%' and trying to convert to float
                cleared_text = cleared_text \
                    .replace(' ', '').replace('%', '').replace('+', '') \
                    .replace(',', '.').replace('−', '-')
                
                # check sign
                if cleared_text[0] == '-':
                    sign = -1
                    cleared_text = cleared_text[1:]
                else:
                    sign = 1
                
                # convert
                if cleared_text.isnumeric() \
                    or cleared_text.replace('.', '').isnumeric() and cleared_text.count('.') == 1:
                    value = sign * float(cleared_text)
                else:
                    value = cleared_text
                
            else:
                value = cleared_text
            
            row.append(value)
            column_index += 1

        # save to DataFrame
        df.loc[cur_row] = row
        cur_row += 1
    
    return df
    
def parse_pagination(page: BeautifulSoup) -> list[dict]:
    r"""Parses page (BeautifulSoup) and return dictionary with parameters of pagination
    """
    pagination = {}
    div = page.find('div', {'data-module': 'ui.pagination'})
    options = div.attrs['data-options']
    for option in options.split(';'):
        key_value = option.split(':')
        if len(key_value) == 2:
            pagination[key_value[0].strip()] = key_value[1].strip()
    return pagination


# get the main page
print('Read the main page')
page = get_page(URL)

# read the pagination parameters
pagination = parse_pagination(page)

# compute the number of pages
pages_count = int(pagination['totalItems']) // int(pagination['itemsPerPage'])
if pages_count * int(pagination['itemsPerPage']) < int(pagination['totalItems']):
    pages_count += 1

# list of DataFrames
dfs = []

# read all the pages and parse them
for num_page in range(1, pages_count + 1):
    print(f'Page parsing in progress: {num_page/pages_count*100:2.1f}%', end='\r')
    if num_page == 1:
        dfs.append(parse_table(page))
    else:
        dfs.append(parse_table(get_page(f'{URL}?{pagination["getParamName"]}={num_page}')))
print('\nPage parsing done')

# create the main DataFrame
df = pd.concat(dfs, ignore_index=True)
print(df.info())

# export DataFrame to MS Excel file
print('Save data to MS Excel file')
df.to_excel('banki.xlsx', index=False)
print('Done')

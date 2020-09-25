# das-boot
A jupyter notebook to scrape sail boat listings to a pandas dataframe for graphing and storing in CSV.

Scrapes the following sites:
- [nettivene](http://nettivene.com/)
- [yachtworld](https://www.yachtworld.com/)
- [boat24](https://www.boat24.com/)
- [theyachtmarket](https://www.theyachtmarket.com)
- [scanboat](https://www.scanboat.com/en)

## Instructions
[Get Jupyter](https://jupyter.org/install), I suggest [miniconda](https://docs.conda.io/en/latest/miniconda.html).

Copy-paste das-boot.py into a fresh jupyter notebook.

Try something like
```
summary(
    listings(
        'Swan',
        max_year=1990,
    )
)
```
in a new cell.

Run the whole notebook. Calls to `listings` will generate `.csv` files of the results, if you prefer continuing in a spreadsheet.

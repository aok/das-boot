# das-boot
A jupyter notebook to scrape sail boat listings to a pandas dataframe for graphing and storing in CSV.

## Instructions
[Get Jupyter](https://jupyter.org/install), I suggest [miniconda](https://docs.conda.io/en/latest/miniconda.html).

Copy-paste das-boot.py into a fresh jupyter notebook.

Try something like in a new cell
```
summary(
    listings(
        'Swan',
        max_year=1990,
    )
)
```

Run the whole notebook.

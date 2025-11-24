## Sentiment Index

A tool for collecting and analyzing text from U.S. federal government websites.  
It scrapes each site's homepage, extracts visible text, and uses a local LLM to detect partisan or accusatory language.


### Workflow

```mermaid
flowchart TD
    A[urls.txt - 
    List of .gov sites] --> B[batch_homepage_scraper.py Fetch + Clean HTML]
    B --> C[homepages.jsonl 
    Raw text from each site]
    C --> D[sentiment_analysis.py
    Send to local LLM]
    D --> E[homepages_with_sentiment_llm.jsonl
    Classified output]
    E --> F[Results & Insights
    Partisan vs Neutral Labels]

    subgraph Local LLM
        D1[openai/gpt-oss-20b model]
    end

    D --> D1
    D1 --> D

    classDef file fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px,color:#1b5e20;
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:1px,color:#0d47a1;
    classDef result fill:#fff3e0,stroke:#ef6c00,stroke-width:1px,color:#e65100;

    class A file;
    class B process;
    class C file;
    class D process;
    class D1 process;
    class E file;
    class F result;
```

### What's working
* Scrape .gov sites from a manual list
* send data to an LLM and get back data
* plot output in a jupyter notebook

### What needs work
* detect when .gov list is updated
* periodic job scraping data
* script to create url list from .gov csv
* test DMR or other method to run multiple instances of an LLM
* hand verify one instance of partisan/neutral for regression tests
* check "unknown" with http status code 200 to verify site doesnt work/return 
* regression testing (pytest?) to test LLMs against each other
* sentimentor repeatability, if i run it 10x do i get the same results? deterministic?
* check sentimentor without truncate options
* if i have a lot of datasets, is it worth sagemaker/mturk ?
* add timestamps / total time to collect and sentiment runs
* processor and code logging, grafana
* vars or flags for sentimentor's model name, in/out files
* database results instead of json files
* setup a queue to run data through LLMs
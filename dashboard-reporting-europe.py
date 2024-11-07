# -*- coding: utf-8 -*-

import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
import requests
from urllib.parse import quote_plus

external_stylesheets = [dbc.themes.BOOTSTRAP, 'https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = 'Reporting HVD Europe'

datagouv_url = "https://www.data.gouv.fr/"
endpoint = "https://data.europa.eu/sparql"
headers = {
    'Accept': 'application/sparql-results+json',
    'Content-Type': 'application/x-www-form-urlencoded'
}
licenses = {
    "https://www.etalab.gouv.fr/wp-content/uploads/2014/05/Licence_Ouverte.pdf": "[Licence Ouverte 1.0](https://www.etalab.gouv.fr/wp-content/uploads/2014/05/Licence_Ouverte.pdf)",
    "https://www.etalab.gouv.fr/licence-ouverte-open-licence": "[Licence Ouverte 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence)",
}
session = requests.Session()


def query_to_df(query, loop=True):
    def _get_from_query(query):
        params = {
            'query': query,
            'timeout': 10000000,
        }
        r = session.post(endpoint, headers=headers, data=params)
        r.raise_for_status()
        r = r.json()
#         print(r)
        return pd.DataFrame([{
            _: k.get(_, {}).get("value") for _ in r["head"]["vars"]
        } for k in r["results"]["bindings"]])

    if loop:
        dfs = []
        batch_size = 100
        offset = 0
        while True:
            df = _get_from_query(query + f" OFFSET {offset} LIMIT {batch_size}")
            # print(offset//batch_size)
            # print(offset, len(df))
            dfs.append(df)
            offset += batch_size
            if len(df) < batch_size:
                break
        df = pd.concat(dfs, ignore_index=True)
    else:
        df = _get_from_query(query)
    return df


catalog_query = """prefix dcat:  <http://www.w3.org/ns/dcat#>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dct: <http://purl.org/dc/terms/>

select distinct ?catalog ?catalog_title
where {
?catalog dcat:dataset ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?catalog dct:title ?catalog_title.
}
LIMIT 20
"""

datasets_query = """prefix dct: <http://purl.org/dc/terms/>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dcat:  <http://www.w3.org/ns/dcat#>

select distinct ?d ?title ?cat_label where {
<$CATALOG$> ?cp ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?d a dcat:Dataset.
?d dcat:distribution ?dist.
optional { ?d dct:title ?title.
     FILTER ( langMatches( lang(?title),  "" ))
}
optional { ?d r5r:hvdCategory ?category. }
OPTIONAL {?category skos:prefLabel ?cat_label. FILTER langMatches( lang(?cat_label),  "fr" )}
?d dct:publisher <$ORGA$>.
}
"""

# resources_query = """prefix dct: <http://purl.org/dc/terms/>
# prefix r5r: <http://data.europa.eu/r5r/>
# prefix dcat:  <http://www.w3.org/ns/dcat#>

# select distinct ?d ?title ?cat_label ?license ?res_title ?accessURL ?downloadURL where {
# <$CATALOG$> ?cp ?d.
# ?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
# ?d a dcat:Dataset.
# ?d dcat:distribution ?dist.
# optional { ?d dct:title ?title.
#      FILTER ( langMatches( lang(?title),  "" ))
# }
# optional { ?d r5r:hvdCategory ?category. }
# OPTIONAL {?category skos:prefLabel ?cat_label. FILTER langMatches( lang(?cat_label),  "fr" )}
# ?d dct:publisher <$ORGA$>.
# optional { ?dist dcat:accessURL ?accessURL. }
# optional { ?dist dcat:downloadURL ?downloadURL. }
# optional { ?dist dct:title ?res_title.
#      FILTER ( langMatches( lang(?res_title),  "" ))
# }
# optional { ?dist dct:license ?license. }
# }
# """


def build_resource_link(resource_download_link):
    try:
        resource_id = resource_download_link.split('/')[-1]
        dataset_id = session.get(
            datagouv_url + f"api/2/datasets/resources/{resource_id}/"
        ).json()["dataset_id"]
        return datagouv_url + 'fr/datasets/' + dataset_id + '/#/resources/' + resource_id
    except Exception:
        print(resource_download_link)


# %% APP LAYOUT:
app.layout = dbc.Container(
    [
        dbc.Row([
            html.H3("Reporting HVD sur data.europa",
                    style={
                        "padding": "5px 0px 10px 0px",  # "padding": "top right down left"
                    }),
        ]),
        dbc.Row([
            html.H5('Sélectionner un catalogue source'),
            dbc.Col([
                dcc.Dropdown(
                    id="catalog_dropdown",
                    placeholder="data.gov.be, GovData...",
                    value="http://data.europa.eu/88u/catalogue/plateforme-ouverte-des-donnees-publiques-francaises",
                    clearable=True,
                ),
            ],
                width=6,
            ),
            dbc.Col([
                dcc.Clipboard(
                    content=catalog_query,
                    title="Copier la requête de récupération des catalogues",
                    style={
                        "display": "inline-block",
                        "fontSize": 20,
                        "verticalAlign": "top",
                    },
                ),
            ],
                width=2,
            ),
            dbc.Col([
                dbc.Button(
                    id='refresh_button',
                    children='Rafraîchir les données'
                ),
            ],
                width=4,
            ),
            html.H5('Rechercher un producteur'),
            dbc.Col([
                dcc.Dropdown(
                    id="producteur_dropdown",
                    placeholder="Météo France, Shom...",
                    clearable=True,
                ),
            ],
                width=8,
            ),
            dbc.Col([
                dcc.Clipboard(
                    id="producteur_clipboard",
                    title="Copier la requête de récupération des producteurs",
                    style={
                        "display": "inline-block",
                        "fontSize": 20,
                        "verticalAlign": "top",
                    },
                ),
            ],
                width=2,
            ),
        ],
            style={"padding": "0px 0px 5px 0px"},
        ),
        html.Div(id="download_div"),
        dcc.Loading(id='loader'),
    ])

# %% Callbacks


@app.callback(
    Output('catalog_dropdown', 'options'),
    [Input('refresh_button', 'n_clicks')]
)
def resfresh_catalog(click):
    catalog = query_to_df(catalog_query, loop=False)
    return [{
        "label": row["catalog_title"],
        "value": row["catalog"],
    } for _, row in catalog.iterrows()]


@app.callback(
    [
        Output('producteur_dropdown', 'options'),
        Output('producteur_dropdown', 'value'),
        Output('producteur_clipboard', 'content'),
    ],
    [Input('catalog_dropdown', 'value')],
)
def resfresh_producteurs(catalog):
    q = """prefix dct: <http://purl.org/dc/terms/>
    prefix r5r: <http://data.europa.eu/r5r/>
    prefix dcat:  <http://www.w3.org/ns/dcat#>

    select distinct ?pub_url ?orga where {
    <$CATALOG$>  ?cp ?d.
    ?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
    ?d dct:publisher ?pub_url.
    optional { ?pub_url foaf:name ?orga. }
    }
    """.replace("$CATALOG$", catalog)
    orgas = query_to_df(q)
    return [{
        "label": row["orga"],
        "value": row["pub_url"],
    } for _, row in orgas.sort_values(by="orga").iterrows()], None, q


@app.callback(
    Output('download_div', 'children'),
    [
        Input('producteur_dropdown', 'value'),
        Input('catalog_dropdown', 'value'),
    ]
)
def update_download_div(orga_url, catalog):
    if not orga_url or not catalog:
        return []
    return dbc.Row([
        dbc.Col([
            dbc.Button(
                id="download_csv_button",
                children="Télécharger les données en csv",
            ),
            dcc.Download(id="download"),
        ],
            width=3,
        ),
        dbc.Col([
            dcc.Clipboard(
                content=datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog),
                title="Copier la requête de récupération des jeux de données",
                style={
                    "display": "inline-block",
                    "fontSize": 20,
                    "verticalAlign": "top",
                },
            ),
        ],
            width=2,
        ),
    ])


@app.callback(
    Output('download', 'data'),
    [Input('download_csv_button', 'n_clicks')],
    [
        State('producteur_dropdown', 'value'),
        State('catalog_dropdown', 'value'),
    ],
    prevent_initial_call=True,
)
def download_csv(click, orga_url, catalog):
    if not orga_url:
        raise PreventUpdate
    query = datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
    url = (
        endpoint
        + "?default-graph-uri=&query="
        + quote_plus(query, safe='*')
        + "&format=text%2Fcsv&timeout=120000&signal_void=on"
    )
    return dict(content=requests.get(url).text, filename="hvd.csv")


@app.callback(
    Output('loader', 'children'),
    [
        Input('producteur_dropdown', 'value'),
        Input('catalog_dropdown', 'value'),
    ],
)
def update_markdown(orga_url, catalog):
    if not orga_url or not catalog:
        return []
    query = datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
    print(query)
    datasets = query_to_df(query, loop=True)
    markdown = ""
    if "francaises" in catalog:
        markdown += f"##### [Lien vers les HVD de l'organisation sur data.gouv.fr]({orga_url + '?tag=hvd#/datasets'})\n"
    markdown += (
        f"#### {len(datasets)} jeu{'x' if len(datasets) > 1 else ''} de données HVD "
        f"reporté{'s' if len(datasets) > 1 else ''} à l'Europe :\n"
    )
    for _, row in datasets.sort_values(by="title").iterrows():
        markdown += f"- [{row['title']}]({row['d']}) (catégorie `{row['cat_label']}`)\n"

    # print(markdown)
    return dcc.Markdown(
        children=markdown,
        link_target="_blank",
        # dangerously_allow_html=True
    )


# retrieving resources is too slow, maybe we'll come back to this later
# @app.callback(
#     Output('loader', 'children'),
#     [Input('producteur_dropdown', 'value')],
#     [State('catalog_dropdown', 'value')],
# )
# def update_markdown(orga_url, catalog):
#     if not orga_url:
#         raise PreventUpdate
#     query = resources_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
#     print(query)
#     resources = query_to_df(query, loop=True)
#     resources['resourceLink'] = resources['accessURL'].apply(build_resource_link)
#     markdown = (
#         f"##### [Lien vers les HVD de l'organisation sur data.gouv.fr]({orga_url + '?tag=hvd#/datasets'})\n"
#         f"#### {resources['d'].nunique()} "
#         f"jeu{'x' if resources['d'].nunique() > 1 else ''} de données HVD "
#         f"reporté{'s' if resources['d'].nunique() > 1 else ''} à l'Europe :\n"
#     )
#     for dataset in resources["title"].unique():
#         restr = resources.loc[resources["title"] == dataset]
#         dataset_url = restr["d"].unique()[0]
#         cat_label = ", ".join(restr["cat_label"].unique())
#         license = (
#             restr["license"].unique()[0]
#             if restr['license'].nunique() == 1
#             else 'plusieurs licences renseignées'
#         )
#         # without collapse
#         # markdown += f"- [{dataset}]({dataset_url}) ({len(restr)} ressource{'s' if len(restr) > 1 else ''})\n"
#         # for _, row in restr.iterrows():
#         #     markdown += f"   - [{row['res_title']}]({row['resourceLink']})\n"

#         # with collapse
#         markdown += (
#             f"###### [{dataset}]({dataset_url}) (catégorie{'s' if restr['cat_label'].nunique() > 1 else ''} `{cat_label}`, "
#             f"{licenses.get(license, license)})\n\n"
#             "<details>\n\n"
#             f"<summary>Voir {len(restr)} ressource{'s' if len(restr) > 1 else ''}</summary>\n\n"
#         )
#         for _, row in restr.iterrows():
#             if row['resourceLink']:
#                 markdown += f"- [{row['res_title']}]({row['resourceLink']}) : {row['downloadURL']}\n"
#             else:
#                 markdown += f"- {row['res_title']} /!\\ cette ressource n'existe plus\n"
#         markdown += "\n</details>\n\n"

#     # print(markdown)
#     return dcc.Markdown(
#         children=markdown,
#         link_target="_blank",
#         dangerously_allow_html=True
#     )


# %%
if __name__ == '__main__':
    app.run_server(debug=False, port=8057)

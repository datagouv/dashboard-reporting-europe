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

producteurs_query = """prefix dct: <http://purl.org/dc/terms/>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dcat:  <http://www.w3.org/ns/dcat#>

select distinct ?pub_url ?orga where {
<$CATALOG$>  ?cp ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?d dct:publisher ?pub_url.
optional { ?pub_url foaf:name ?orga. }
}
"""

datasets_query = """prefix dct: <http://purl.org/dc/terms/>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dcat:  <http://www.w3.org/ns/dcat#>

select distinct ?d ?title ?cat_label ?landing_page ?contact_point where {
<$CATALOG$> ?cp ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?d a dcat:Dataset.
?d dct:publisher <$ORGA$>.
optional { ?d dcat:landingPage ?landing_page. }
optional { ?d dcat:contactPoint ?contact_point. }
optional { ?d dct:title ?title.
     filter ( langMatches( lang(?title),  "" ))
}
optional { ?d r5r:hvdCategory ?category. }
optional {?category skos:prefLabel ?cat_label. filter langMatches( lang(?cat_label),  "fr" )}
}
"""

dataservices_in_datasets_query = """prefix dct: <http://purl.org/dc/terms/>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dcat:  <http://www.w3.org/ns/dcat#>

select distinct ?d ?api_title ?access_url ?endpoint_url ?endpoint_description where {
<http://data.europa.eu/88u/catalogue/plateforme-ouverte-des-donnees-publiques-francaises> ?cp ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?d a dcat:Dataset.
?d dct:publisher <$ORGA$>.
?d dcat:distribution ?dist.
?dist dcat:accessURL ?access_url.
?dist dcat:accessService ?accserv.
optional { ?accserv dct:title ?api_title. }
optional { ?accserv dcat:endpointURL ?endpoint_url. }
optional { ?accserv dcat:endpointDescription ?endpoint_description. }
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
#      filter ( langMatches( lang(?title),  "" ))
# }
# optional { ?d r5r:hvdCategory ?category. }
# optional {?category skos:prefLabel ?cat_label. filter langMatches( lang(?cat_label),  "fr" )}
# ?d dct:publisher <$ORGA$>.
# optional { ?dist dcat:accessURL ?accessURL. }
# optional { ?dist dcat:downloadURL ?downloadURL. }
# optional { ?dist dct:title ?res_title.
#      filter ( langMatches( lang(?res_title),  "" ))
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


def placeholder_from_options(options):
    return ', '.join(sorted(
        list(set([o['label'] for o in options])),
        key=len)[:3]
    ) + "..."


def button_clipboard(id):
    return dbc.Button("Voir requête", id=id, outline=True, color="info")


def build_sparql_url(query):
    return (
        endpoint
        + "?default-graph-uri=&query="
        + quote_plus(query, safe='*')
        + "&format=text%2Fcsv&timeout=120000&signal_void=on"
    )


# %% APP LAYOUT:
app.layout = dbc.Container(
    [
        dbc.Row([
            dbc.Col([
                html.H3("[BETA] Reporting HVD sur data.europa"),
            ], width=9),
            dbc.Col([
                html.I('by data.gouv.fr'),
            ], width=3),
        ],
            style={
                "padding": "5px 0px 10px 0px",  # "padding": "top right down left"
            },
        ),
        dbc.Row([
            html.H5('Sélectionner un catalogue source'),
            dbc.Col([
                dcc.Dropdown(
                    id="catalog_dropdown",
                    value="http://data.europa.eu/88u/catalogue/plateforme-ouverte-des-donnees-publiques-francaises",
                    clearable=True,
                ),
            ],
                width=6,
            ),
            dbc.Col([
                button_clipboard("catalog_query_button"),
            ],
                width=2,
            ),
            dbc.Col([
                dbc.Button(
                    id='refresh_button',
                    children='Rafraîchir les données',
                    outline=True,
                    color="primary",
                ),
            ],
                width=4,
            ),
            html.H5('Rechercher un producteur'),
            dbc.Col([
                dcc.Dropdown(
                    id="producteur_dropdown",
                    clearable=True,
                ),
            ],
                width=8,
            ),
            dbc.Col([
                button_clipboard("producteur_query_button"),
            ],
                width=2,
            ),
        ],
            style={"padding": "0px 0px 5px 0px"},
        ),
        html.Div(id="ghost_div", children=[
            button_clipboard("datasets_query_button"),
        ], style={'display': "none"}),
        html.Div(id="download_div"),
        dcc.Loading(id='loader'),
        dbc.Modal(id="query_modal", is_open=False, children=[
             dbc.Button(
                "Fermer",
                id="close_modal_button",
             ),
        ]),
    ])

# %% Callbacks


@app.callback(
    [
        Output('catalog_dropdown', 'options'),
        Output('catalog_dropdown', 'placeholder'),
    ],
    [Input('refresh_button', 'n_clicks')],
)
def resfresh_catalog(click):
    catalog = query_to_df(catalog_query, loop=False)
    options = [{
        "label": row["catalog_title"],
        "value": row["catalog"],
    } for _, row in catalog.iterrows()]
    return options, placeholder_from_options(options)


@app.callback(
    [
        Output('producteur_dropdown', 'options'),
        Output('producteur_dropdown', 'value'),
        Output('producteur_dropdown', 'placeholder'),
    ],
    [Input('catalog_dropdown', 'value')],
)
def resfresh_producteurs(catalog):
    q = producteurs_query.replace("$CATALOG$", catalog)
    orgas = query_to_df(q)
    options = [{
        "label": row["orga"],
        "value": row["pub_url"],
    } for _, row in orgas.drop_duplicates(subset="pub_url").sort_values(by="orga").iterrows()]
    return options, None, placeholder_from_options(options)


@app.callback(
    [
        Output('download_div', 'children'),
        Output('ghost_div', 'style'),
    ],
    [
        Input('producteur_dropdown', 'value'),
        Input('catalog_dropdown', 'value'),
    ],
)
def update_download_div(orga_url, catalog):
    if not orga_url or not catalog:
        return [], {'display': "none"}
    return dbc.Row([
        dbc.Col([
            dbc.Button(
                id="download_csv_button",
                children="Télécharger les données en csv",
                outline=True,
                color="primary",
            ),
            dcc.Download(id="download"),
        ],
            width=3,
        ),
    ]), {'display': 'block', "padding": "5px 0px 10px 0px"}


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
    datasets = pd.read_csv(build_sparql_url(query))
    ds_query = dataservices_in_datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
    dataservices = pd.read_csv(build_sparql_url(ds_query))
    if len(dataservices):
        merged = pd.merge(
            datasets,
            # only keeping one dataservice per dataset for now
            dataservices.drop_duplicates(subset="d"),
            on="d",
            how="left",
        )
    else:
        merged = datasets.copy()
    return dict(content=merged.to_csv(index=False), filename="hvd.csv")


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
    ds_query = dataservices_in_datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
    # print(query)
    datasets = query_to_df(query, loop=True)
    dataservices = query_to_df(ds_query, loop=True)
    markdown = ""
    if "francaises" in catalog:
        markdown += f"##### [Lien vers les HVD de l'organisation sur data.gouv.fr]({orga_url + '?tag=hvd#/datasets'})\n"
    nb = datasets['d'].nunique()
    nb_ds = len(dataservices)
    md_ds = ""
    if nb_ds:
        md_ds = f"et {nb_ds} dataservice{'s' if nb_ds > 1 else ''} "
    markdown += (
        f"#### {nb} jeu{'x' if nb > 1 else ''} de données HVD {md_ds}"
        f"reporté{'s' if nb > 1 else ''} à l'Europe :\n"
    )
    data = {}
    for _, row in datasets.sort_values(by="title").iterrows():
        if row['d'] not in data:
            data[row['d']] = {
                'title': row['title'],
                'cat_labels': [row['cat_label']],
                'landing_page': row['landing_page'],
            }
        else:
            data[row['d']]['cat_labels'].append(row['cat_label'])
    for d in data:
        source = (
            f"[lien vers la source]({data[d]['landing_page']})"
            if data[d]['landing_page']
            else "⚠️ lien vers la source manquant"
        )
        markdown += (
            f"- [{data[d]['title']}]({d}) ({source}) "
            f"(catégorie{'s' if len(data[d]['cat_labels']) > 1 else ''} "
            + ', '.join([f'`{cl}`' for cl in data[d]["cat_labels"]]) + ")\n"
        )
        if not nb_ds:
            continue
        restr_ds = dataservices.loc[dataservices['d'] == d]
        if len(restr_ds):
            for _, row in restr_ds.iterrows():
                description = "⚠️ pas de description"
                if row["endpoint_description"]:
                    description = f"[description]({row['endpoint_description']})"
                markdown += (
                    f"   - API [{row['api_title']}]({row['access_url']}) "
                    f"([endpoint]({row['endpoint_url']}), {description})\n"
                )

    # print(markdown)
    return dcc.Markdown(
        children=markdown,
        link_target="_blank",
        # dangerously_allow_html=True
    )


@app.callback(
    [
        Output('query_modal', 'children'),
        Output('query_modal', 'is_open'),
    ],
    [
        Input('catalog_query_button', 'n_clicks'),
        Input('producteur_query_button', 'n_clicks'),
        Input('datasets_query_button', 'n_clicks'),
        Input('close_modal_button', 'n_clicks'),
    ],
    [
        State('catalog_dropdown', 'value'),
        State('producteur_dropdown', 'value')
    ],
    prevent_initial_call=True,
)
def show_modal(catalog_click, producteur_click, datasets_click, close, catalog, orga_url):
    trigger = dash.ctx.triggered[0]["prop_id"].split("_")[0]
    header = ""
    query = ""
    if close:
        return [dbc.Button(
            "Fermer",
            id="close_modal_button",
        ),], False
    if trigger == "catalog":
        header = "Requête de récupération des catalogues"
        query = catalog_query
    if trigger == "producteur":
        header = "Requête de récupération des producteurs du catalogue sélectionné"
        query = producteurs_query.replace("$CATALOG$", catalog)
    if trigger == "datasets":
        header = "Requête de récupération des jeux de données du producteur sélectionné"
        query = datasets_query.replace("$ORGA$", orga_url).replace("$CATALOG$", catalog)
    return [
        dbc.ModalHeader(dbc.ModalTitle(header), close_button=False),
        dbc.ModalBody(dcc.Markdown(f"```sql\n{query}```")),
        dbc.ModalFooter(
            dbc.Button(
                "Fermer",
                id="close_modal_button",
                outline=True,
                color="danger",
            )
        ),
    ], True


# retrieving distributions is too slow, maybe we'll come back to this later
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

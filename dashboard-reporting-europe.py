# -*- coding: utf-8 -*-

import dash
# from dash import dash_table
from dash import dcc
from dash import html
# import dash_daq as daq
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

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
            'query': query
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
        batch_size = 10000
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


resources_query = """prefix dct: <http://purl.org/dc/terms/>
prefix r5r: <http://data.europa.eu/r5r/>
prefix dcat:  <http://www.w3.org/ns/dcat#>

select distinct ?d ?title ?cat_label ?license ?res_title ?accessURL where {
<http://data.europa.eu/88u/catalogue/plateforme-ouverte-des-donnees-publiques-francaises> ?cp ?d.
?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
?d a dcat:Dataset.
?d dcat:distribution ?dist.
optional { ?d dct:title ?title.
     FILTER ( langMatches( lang(?title),  "" ))
}
optional { ?d r5r:hvdCategory ?category. }
OPTIONAL {?category skos:prefLabel ?cat_label. FILTER langMatches( lang(?cat_label),  "fr" )}
?d dct:publisher <$ORGA$>.
optional { ?dist dcat:accessURL ?accessURL. }
optional { ?dist dct:title ?res_title.
     FILTER ( langMatches( lang(?res_title),  "" ))
}
optional { ?dist dct:license ?license. }
}
"""


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
            html.H5('Rechercher un producteur'),
            dbc.Col([
                dcc.Dropdown(
                    id="producteur_dropdown",
                    placeholder="Météo France, Shom...",
                    clearable=True,
                ),
            ]),
            dbc.Col([
                dbc.Button(
                    id='refresh_button',
                    children='Rafraîchir les données'
                ),
            ]),
        ],
            style={"padding": "0px 0px 5px 0px"},
        ),
        dcc.Loading(id='loader'),
    ])

# %% Callbacks


@app.callback(
    Output('producteur_dropdown', 'options'),
    [Input('refresh_button', 'n_clicks')]
)
def resfresh_producteurs(click):
    orgas = query_to_df("""prefix dct: <http://purl.org/dc/terms/>
    prefix r5r: <http://data.europa.eu/r5r/>
    prefix dcat:  <http://www.w3.org/ns/dcat#>

    select distinct ?pub_url ?orga where {
    <http://data.europa.eu/88u/catalogue/plateforme-ouverte-des-donnees-publiques-francaises>  ?cp ?d.
    ?d r5r:applicableLegislation <http://data.europa.eu/eli/reg_impl/2023/138/oj>.
    ?d dct:publisher ?pub_url.
    optional { ?pub_url foaf:name ?orga. }
    }
    """)
    return [{
        "label": row["orga"],
        "value": row["pub_url"],
    } for _, row in orgas.iterrows()]


@app.callback(
    Output('loader', 'children'),
    [Input('producteur_dropdown', 'value')]
)
def update_graph(orga_url):
    if not orga_url:
        raise PreventUpdate
    query = resources_query.replace("$ORGA$", orga_url)
    print(query)
    resources = query_to_df(query, loop=True)
    resources['resourceLink'] = resources['accessURL'].apply(build_resource_link)
    markdown = (
        f"##### [Lien vers la page de l'organisation]({orga_url})\n"
        f"#### {resources['d'].nunique()} "
        f"HVD reporté{'s' if resources['d'].nunique() > 1 else ''} à l'Europe :\n"
    )
    for dataset in resources["title"].unique():
        restr = resources.loc[resources["title"] == dataset]
        dataset_url = restr["d"].unique()[0]
        cat_label = restr["cat_label"].unique()[0]
        license = (
            restr["license"].unique()[0]
            if restr['license'].nunique() == 1
            else 'plusieurs licences renseignées'
        )
        # without collapse
        # markdown += f"- [{dataset}]({dataset_url}) ({len(restr)} ressource{'s' if len(restr) > 1 else ''})\n"
        # for _, row in restr.iterrows():
        #     markdown += f"   - [{row['res_title']}]({row['resourceLink']})\n"

        # with collapse
        markdown += (
            f"###### [{dataset}]({dataset_url}) (catégorie `{cat_label}`, "
            f"{licenses.get(license, license)})\n\n"
            "<details>\n\n"
            f"<summary>Voir {len(restr)} ressource{'s' if len(restr) > 1 else ''}</summary>\n\n"
        )
        for _, row in restr.iterrows():
            if row['resourceLink']:
                markdown += f"- [{row['res_title']}]({row['resourceLink']})\n\n"
            else:
                markdown += f"- {row['res_title']} /!\\ cette ressource n'existe plus\n\n"
        markdown += "</details>\n\n"

    # print(markdown)
    return dcc.Markdown(
        children=markdown,
        link_target="_blank",
        dangerously_allow_html=True
    )


# %%
if __name__ == '__main__':
    app.run_server(debug=False, use_reloader=False, port=8051)

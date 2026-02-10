import sys, os

fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)
from panels import ModelSection

from dash import dcc, html
from dash import Dash, callback_context
from dash.exceptions import PreventUpdate
from dash_bootstrap_components import Button, ButtonGroup, themes
import dash_bootstrap_components as dbc
import dash_flexlayout as dfl

from temframe import TEMframe

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "sea anemone"

import session
sesh = session.Session.from_folder("C:/Users/au646858/OneDrive - Aarhus Universitet/Documents/anemone_projects/eliya_spring_kenya/")

test_panel = ModelSection(dataframe=sesh.models)
panels = [test_panel]
nodes = [node for panel in panels for node in panel.to_nodes()]

print(test_panel.settings.schema)

test_panel_layout = test_panel.layout_dict
test_panel_layout['active'] = True

layout = config = {
    "global": {"tabEnableClose":True, "tabEnableFloat": True},
    "borders":[
        {
          "type": "border",
          "location":"bottom",
          "size": 100,
          "children": [
              {
              "type": "tab",
              "name": "four",
              "component": "text"
              }
            ]
        }
    ],    "layout": {
        "type": "row",
        "weight": 50,
        "children": [
            {
                "type": "tabset",
                "weight": 50,
                "children": [
                    test_panel_layout
                ]
            }
        ]
    }
}

flex_layout = dfl.FlexLayout(id="flex-layout", children=nodes, model=layout, useStateForModel=False)

app.layout =  flex_layout

for panel in panels:
    panel.add_callbacks(app)

app.run(port=8050, debug=True)
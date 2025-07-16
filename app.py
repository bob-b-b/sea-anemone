from panels import *

import dash_mantine_components as dmc
from dash import Dash

app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')
app.title = "sea anemone"


from dash import dcc
import example_panels as ep
m1 = Map(data=ep.df)
dbdt1 = dbdtSounding(lm_time=ep.lm.time.mean(0),
                    lm_data=ep.lm.data.mean(0),
                    hm_time=ep.hm.time.mean(0),
                    hm_data=ep.hm.data.mean(0))

rhoa1 = rhoaSounding(lm_time=ep.lm.time.mean(0),
                    lm_data=ep.lm.data.mean(0),
                    hm_time=ep.hm.time.mean(0),
                    hm_data=ep.hm.data.mean(0))


dbdt2 = dbdtSection(lm_time=ep.lm.time,
            lm_data=ep.lm.data,
            hm_time=ep.hm.time,
            hm_data=ep.hm.data)
u1 = Upload()

panels = [u1, m1, dbdt1, dbdt2, rhoa1]
nodes = [node for panel in panels for node in panel.to_nodes()]
config = {
    "global": {"tabEnableClose": True, "tabEnableFloat": True},
    "borders": [
        {"type": "border", "location": "right", "size": 200, "children": [                    
                    {
                        "type": "tab",
                        "name": "One",
                        "component": "text",
                        "id": "side-1",
                        "tabEnableClose": False,
                    },
        ]},
    ],
    "layout": {
        "type": "row",
        "weight": 100,
        "children": [{
                "type": "tabset",
                "weight": 50,
                "children": [
                    u1.layout_dict,
                    m1.layout_dict,
                ],
            },
            {
                "type": "tabset",
                "weight": 50,
                "children": [
                    dbdt1.layout_dict,
                    dbdt2.layout_dict,
                    rhoa1.layout_dict,
                ],
            },
        ],
    },
}

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dfl.FlexLayout(
    id="flex-layout",
    model=config,
    children=nodes,
    useStateForModel=False,
    
)]
)

for panel in panels:
    panel.add_callbacks(app)

@app.callback(
    [ 
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM',     'figure', allow_duplicate=True),
        Output('rhoa',     'figure', allow_duplicate=True)
    ],
    Input('map', 'selectedData'),
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def update_dbdt(selected_data):
    if not selected_data or 'points' not in selected_data:
        raise PreventUpdate

    # Extract selected points
    selected_points = [point['pointIndex'] for point in selected_data['points']]

    dbdt1.hm_data = ep.hm.data[selected_points]*1.
    dbdt1.lm_data = ep.lm.data[selected_points]*1.
    
    rhoa1.hm_data = ep.hm.data[selected_points]*1.
    rhoa1.lm_data = ep.lm.data[selected_points]*1.        

    dbdt2.hm_data = ep.hm.data[selected_points]*1.
    dbdt2.lm_data = ep.lm.data[selected_points]*1.
    dbdt2.hm_time = ep.hm.time[selected_points]*1.
    dbdt2.lm_time = ep.lm.time[selected_points]*1.
    return dbdt1.render(), dbdt2.render(), rhoa1.render()



app.run(debug=True, port=8050, dev_tools_hot_reload=True)
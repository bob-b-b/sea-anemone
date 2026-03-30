from basepanel import *
import numpy as np
import pandas as pd

@nosj
class ModelGraphSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    color_by: Literal['site_id', 'misfit'] = 'site_id'
    rho_min: float = 1.0
    rho_max: float = 1000.0

class ModelGraph(Panel):
    highlighted=None
    buffer_len = 50
    buffer_start = 0

    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelGraphSettings(id='model_graph'))
        super().__init__(id='model_graph', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        if self.dataframe is None: return self.empty_render()
        # ...existing code...
        df_layers_long = pd.melt(
            self.dataframe,
            id_vars=['site_id', 'daytime', 'longitude', 'latitude', 'date', 'elevation', 'layer', 'resistivity'],
            value_vars=['top_depth', 'bottom_depth'],
            var_name='depth_type',
            value_name='depth'
        ).sort_values(['site_id', 'daytime', 'layer', 'depth'])

        df_layers_long = df_layers_long.drop(columns=['depth_type'])

        if self.highlighted is None:
            heatmap_df = df_layers_long.set_index('site_id').sort_index(ascending=True)
            buffer_start = self.buffer_start
            buffer_len   = self.buffer_len

            x_values = df_layers_long['site_id'].unique().tolist()
            n_sites  = len(x_values)

            plot_start = max(0, buffer_start)
            plot_end   = min(n_sites, buffer_start + buffer_len)

            x_slice = x_values[plot_start:plot_end]

            fig = px.line(
                df_layers_long[df_layers_long['site_id'].isin(x_slice)],
                x="resistivity",
                y="depth",
                color="site_id",
                labels={
                    "resistivity": "ρ [Ω·m]",  # Unicode rho
                    "site_id": "Site ID"
                },
                title="1D Resistivity Profile",
            )
        else:
            fig = go.Figure(layout=dict(title="1D Resistivity Profile"))
            df_highlighted = df_layers_long[df_layers_long['site_id'] == self.highlighted]
            fig.add_trace(
                go.Scatter(
                    x=df_highlighted["resistivity"],
                    y=df_highlighted["depth"],
                    mode="lines",
                    line=dict(width=2, color='red'),
                    zorder=10,
                    name=f"Site {self.highlighted}"
                ), 
            )
            # fig.add_trace(
            #     go.Scatter(
            #         x=df_layers_long["resistivity"],
            #         y=df_layers_long["depth"],
            #         mode="lines",
            #         line=dict(color='gray'),
            #         name='All Sites'
            #     ), 
            # )



        # Reverse y-axis so depth increases downward
        # fig.update_yaxes(autorange="reversed")
        # fig.update_xaxes(type="log", range=[np.log10(self.settings.rho_min), np.log10(self.settings.rho_max)])
        fig.update_xaxes(title_text='Resistivity [Ω⋅m]',type='log',range=[0, 2.7],showline=True,mirror=True           )

        fig.update_yaxes(
            title_text='Depth [m]',
            range=[180, -0.5],  # depth increasing downward
            showline=True,
            mirror=True,
        )
        return fig        
    
@nosj
class ModelSectionSettings(PanelSettings):
    y_axis: Literal['depth', 'elevation'] = 'depth'
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude', 'distance'] = 'site_id'
    bars: bool=True
    radius: float = 100.

class ModelSection(Panel):
    highlighted: int = None
    buffer_len = 50
    buffer_start = 0
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelSectionSettings(id='model_section'))
        super().__init__(id='model_section', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def initialize(self):
        from __main__ import sesh
        options=['site_id', 'daytime']
        if sesh.lines is not None:
            line_id = np.unique(sesh.lines.line.values)
            options += [f'line {i:02d}' for i in line_id]
        return  html.Div([
                    html.Div(
                        [
                        dcc.Graph(
                        id=self.id,
                        figure=self.render(),
                        mathjax=True,
                        style={"height": "95%"}
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        dbc.Label(
                                            "x-axis",
                                            html_for=self.id + "_axis",
                                            class_name="mb-0",
                                            style={"width": "70px", "textAlign": "right"},
                                        ),
                                        dbc.Select(
                                            id=self.id + "_axis",
                                            options=options,
                                            value="site_id",
                                            style={"width": "120px"},
                                        ),
                                    ],
                                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                ),
                                html.Div(
                                    [
                                        dbc.Label(
                                            "radius",
                                            html_for=self.id + "_radius",
                                            class_name="mb-0",
                                            style={"width": "70px", "textAlign": "right"},
                                        ),
                                        dbc.Input(
                                            id=self.id + "_radius",
                                            value=100.0,
                                            type="number",
                                            step=25.0,
                                            disabled=True,
                                            style={"width": "120px"},
                                        ),
                                    ],
                                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                ),
                            ],
                            style={
                                "position": "absolute",
                                "bottom": "12px",
                                "left": "12px",
                                "display": "flex",
                                "flexDirection": "column",
                                "gap": "8px",
                                "zIndex": 1000,
                                "backgroundColor": "rgba(255,255,255,0.85)",
                                "padding": "6px 8px",
                                "borderRadius": "6px",
                            },
                        ),
                        ],
                        style={"position": "relative", "height": "100%"}
                    ),
                    gear_maker(self.id)],
                    style={'height': '100%'} 
                )
    
    def render_base(self):
        
        if self.dataframe is None: return self.empty_render()
        df = self.dataframe.copy()
        x_axis = self.settings.x_axis

        if 'line' in x_axis:
            from __main__ import sesh
            df = sesh.models.copy()
            df = df.loc[np.abs(df[x_axis.replace('_x', '_y')])<self.settings.radius]
        
        y_axis = self.settings.y_axis
        res_grid = df.pivot_table('resistivity', x_axis, 'center_depth')
        x   = np.sort(np.unique(df[x_axis].values))
        y   = res_grid.columns.values.squeeze()

        if y_axis=='elevation':
            elev= df.pivot_table('elevation', x_axis).values.squeeze()
            depth = res_grid.columns.values
            center_elev = elev[:, None] - depth[None, :]
            d_elev = int(center_elev.max()-center_elev.min())+50
            elev_axis = np.arange(d_elev)+center_elev.min()-25
            dist = np.abs(elev_axis[:, None, None] - center_elev[None, :, :])
            nearest_idx = dist.argmin(axis=-1)  # (n_elev, n_station)

            # Build station index grid
            n_elev, n_station = nearest_idx.shape
            station_idx = np.broadcast_to(
                np.arange(n_station),
                (n_elev, n_station)
            )

            # Direct advanced indexing
            res_grid = res_grid.values[station_idx, nearest_idx]
            heaven = elev_axis[:, None] > elev[None, :]
            hell   = elev_axis[:, None] < (elev[None, :]-depth.max()*1.1)

            res_grid[heaven] = np.nan
            res_grid[hell]   = np.nan

            y = elev_axis
        else:
            res_grid = res_grid.values.T

        if self.settings.bars:
            dx = np.abs(np.diff(x, prepend=0.))
            dx_min = dx.min()*0.49
            res_grid = np.repeat(res_grid, 3, axis=1)
            x = np.repeat(x, 3)
            x[::3] -= dx_min
            x[2::3] += dx_min
            
            dx = np.abs(np.diff(x, prepend=0.))
            x_len = x.max()-x.min()
            needs_gap = dx>0.03*x_len

            if needs_gap.any():
                x_with_gaps = np.zeros(len(x)+2*sum(needs_gap))
                x_with_gaps[:] = np.nan
                i_x = np.arange(len(x))+np.cumsum(2*needs_gap.astype(int))
                x_with_gaps[i_x] = x            
                res_elev_with_gaps = np.zeros(res_grid.shape[:1]+x_with_gaps.shape)
                res_elev_with_gaps[:,:] = np.nan
                res_elev_with_gaps[:, i_x] = res_grid
                x = x_with_gaps*1.
                res_grid = res_elev_with_gaps*1.
        res_grid = np.log10(res_grid)        

        fig = px.imshow(
            res_grid, x=x, y=y,
            aspect='auto',
            origin='lower',
            color_continuous_scale='turbo',
            labels={'x': x_axis.replace('_x', '').replace('_', ' ').strip(), 'y': y_axis, 'color': 'Resistivity [Ω·m]'},
            zmin=0,
            zmax=2.7,
        )
        if y_axis=='depth':
            fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            coloraxis_colorbar=dict(
                tickvals = [0, 1, 2, np.log10(500)],
                ticktext = ["1", "10", "100", "500"],
                orientation="h",     # horizontal
                y=-0.45,              # move below plot
                x=0.5,               # center horizontally
                xanchor="center",
                len=0.5,
                thickness = 10,
                title=dict(
                    text="Resistivity [Ωm]",
                    side="bottom")
                ),
            xaxis=dict(
                title_standoff=4   # default is ~15–20
            ),
            hovermode="x")
        return fig
    
    def render(self):
        if self.dataframe is None: return self.empty_render()
        elif True: return self.render_base()
        else:
            
            df_layers_long = self.dataframe.melt(
                id_vars=[self.settings.x_axis, 'resistivity', 'misfit','doi'],
                value_vars=['top_depth', 'bottom_depth'],
                var_name='depth_type',
                value_name='depth'
            ).sort_values([self.settings.x_axis, 'layer', 'depth'])

            df_layers_long = df_layers_long.drop(columns=['depth_type'])
            df_layers_long['log_resistivity'] = np.log10(df_layers_long['resistivity'])

            heatmap_df = df_layers_long.pivot_table(
                index='depth', columns=self.settings.x_axis, values='log_resistivity'
            )        
            heatmap_df = heatmap_df.sort_index(ascending=True)
            buffer_start = self.buffer_start
            buffer_len   = self.buffer_len

            x_values = heatmap_df.columns.tolist()
            n_sites  = len(x_values)

            plot_start = max(0, buffer_start)
            plot_end   = min(n_sites, buffer_start + buffer_len)

            x_slice = x_values[plot_start:plot_end]
            df_layers_long = df_layers_long[df_layers_long[self.settings.x_axis].isin(x_slice)]

            fig = px.imshow(
                heatmap_df[x_slice],
                aspect='auto',
                origin='lower',
                color_continuous_scale='turbo',
                labels={'x': self.settings.x_axis, 'y': 'Depth [m]', 'color': 'Resistivity [Ω·m]'},
                zmin=0,
                zmax=2.7,
            )
            fig.update_layout(
                coloraxis_colorbar=dict(
                    tickvals = [0, 1, 2, np.log10(500)],
                    ticktext = ["1", "10", "100", "500"],
                    orientation="h",     # horizontal
                    y=-0.45,              # move below plot
                    x=0.5,               # center horizontally
                    xanchor="center",
                    len=0.5,
                    thickness = 10,
                    title=dict(
                text="Resistivity [Ωm]",
                side="bottom"))
            )
            fig.update_layout(
                xaxis=dict(
                    title_standoff=4   # default is ~15–20
                )
            )
            fig.update_layout(hovermode="x")
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(yaxis2=dict(title='Misfit',overlaying='y',side='right',showgrid=False))

            # ---- Misfit only for buffered sites ----
            misfit_df = (
                df_layers_long
                .groupby(self.settings.x_axis)['misfit']
                .first()
                .reset_index()
            )

            misfit_trace = go.Scatter(
                x=misfit_df[self.settings.x_axis],
                y=misfit_df['misfit'],
                mode='lines',
                line=dict(color='black', width=2),
                name='Misfit',
                yaxis='y2'
            )

            y_dashed = misfit_df['misfit'].copy()
            y_dashed[y_dashed <= 8] = np.nan
            y_dashed[y_dashed > 8] = 7.95

            fig.add_trace(go.Scatter(
                x=misfit_df[self.settings.x_axis],
                y=y_dashed,
                mode="lines",
                line=dict(color="rgba(0,0,0,0.7)", dash="dash"),
                showlegend=False,
                yaxis='y2'
            ))


            # misfit_trace.update(
            #     yaxis='y2',
            #     line=dict(color='black', width=2),
            #     name='Misfit',showlegend=True
            # )
            # fig.update_layout(yaxis2=dict(range=[0, 8]))
            # fig.add_trace(go.Scatter(
            #     x=x,
            #     y=y_dashed,
            #     mode="lines",
            #     line=dict(color="rgb(0,0,0,0.7)", dash="dash"),
            #     # hoverinfo="skip",
            #     showlegend=False, yaxis='y2'
            # ))



            fig.add_trace(misfit_trace)

            fig.update_layout(
            legend=dict(x=0.89, y=0.2,xanchor="left",yanchor="top",bgcolor="rgba(255,255,255,0.8)")
                )

            fig.update_layout(yaxis2=dict(title=dict(text="Misfit",standoff=10),overlaying="y",side="right",showgrid=False)
    )
            doi_df = (df_layers_long.groupby(self.settings.x_axis)["doi"].first().reset_index())
            if not doi_df.empty:
                x_min = min(x_slice)
                x_max = max(x_slice)
                y_max = df_layers_long["depth"].max()

                fig.add_trace(
                    go.Scatter(
                        x=np.concatenate([
                            [x_min],
                            doi_df[self.settings.x_axis].values,
                            [x_max],
                            [x_min]
                        ]),
                        y=np.concatenate([
                            [y_max + 50],
                            doi_df["doi"].values,
                            [y_max + 50],
                            [y_max + 50]
                        ]),
                        fill="toself",
                        fillcolor="rgba(255,255,255,0.6)",
                        line=dict(width=0),
                        name="Below DOI",
                    )
                )

            if self.highlighted is not None and self.dataframe is not None:

                selected_df = self.dataframe[self.dataframe["site_id"] == self.highlighted]

                if not selected_df.empty:

                    x_axis = self.settings.x_axis
                    x_value = selected_df[x_axis].iloc[0]

                    x_vals = np.sort(self.dataframe[x_axis].dropna().unique())

                    if len(x_vals) > 1:
                        diffs = np.diff(x_vals)
                        dx = np.median(diffs) * 0.5
                    else:
                        dx = 0.5

                    fig.add_shape(
                        type="rect",
                        x0=x_value - dx,
                        x1=x_value + dx,
                        y0=df_layers_long["depth"].min(),
                        y1=df_layers_long["depth"].max()+20,
                        line=dict(color="black", width=1.5),
                        fillcolor="rgba(0,0,0,0.0)",
                    )

            fig.update_yaxes(
                range=[doi_df["doi"].max()+8, df_layers_long["depth"].min()-8],
                autorange=False,
                #title="Depth [m]"
            )

            fig.update_xaxes(
                range=[x_min, x_max],
                autorange=False
            )
            fig.update_layout(yaxis2=dict(range=[0, 8]))
            return fig
        
        # def add_callbacks(self, app):
        #     super().add_callbacks(app)

        #     @app.callback(
        #         Output(self.id, 'figure', allow_duplicate=True),
        #         Output('data-buffer','data', allow_duplicate=True),
        #         Input('next-buffer', 'data'),
        #         Input('prev-buffer', 'data'),
        #         State('buffer','length'),
        #         prevent_initial_call=True
        #     )
        #     def update_buffer(data,length):
        #         if not ctx.triggered:
        #             raise PreventUpdate
        #         trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        #         highlighted = m1.highlighted
        #         if trigger_id == 'next-buffer':
        #             self.buffer_start += length
        #             if self.buffer_start > len(self.dataframe): self.buffer_start-=length 
        #         elif trigger_id == 'prev-buffer':
        #             self.buffer_start -= length
        #             if self.buffer_start>0: self.buffer_start=0
                    
        #         return self.render(), {"length": length, "start_site": self.buffer_start}
            
        #     @app.callback(
        #         Output(self.id, 'figure', allow_duplicate=True),
        #         Input('next-buffer', 'data'),
        #         prevent_initial_call=True
        #     )
        #     def update_buffer(data,length):
        #         if not ctx.triggered:
        #             raise PreventUpdate
        #         trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        #         highlighted = m1.highlighted
        #         if trigger_id == 'next-buffer':
        #             self.buffer_start += length
        #             if self.buffer_start > len(self.dataframe): self.buffer_start-=length 
        #         elif trigger_id == 'prev-buffer':
        #             self.buffer_start -= length
        #             if self.buffer_start>0: self.buffer_start=0
        #         return self.render()
        #     return fig

    def add_callbacks(self, app):
        super().add_callbacks(app)

        @app.callback(
            self.output, Output(self.id+'_radius', 'disabled'),
            Input(self.id+'_axis', 'value'),
            prevent_initial_call=True
        )
        def update_xaxis(x_axis):
            disabled=True
            if x_axis.startswith('line'):
                line_id = int(float(x_axis.split(' ')[-1]))
                x_axis = f'_line_{line_id:0.0f}_x'
                disabled = False
            self.settings.x_axis=x_axis
            return self.render(), disabled
    
        @app.callback(
            self.output, 
            Input(self.id+'_radius', 'value'),
            prevent_initial_call=True
        )
        def update_radius(radius):
            self.settings.radius=radius
            return self.render()
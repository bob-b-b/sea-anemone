# load data

#%%
import matplotlib.pyplot as plt
import numpy as np

import usf

lm,hm = usf.Sweep.from_usf("O:/Nat-Tech_HGG-Projects/2025_sTEM_DollowSomalia/sTEM Profiler data/sTEM35/2025_0227/USF_Files_dawa river/L001_S001_2025_0227_120804.usf")


# fig,axs = plt.subplots(1,3, sharey=True, sharex=True)
# axs[0].loglog(lm.time.mean(0), lm.data.T, 'k-')
# axs[0].loglog(lm.time.mean(0), lm.data.mean(0))

# axs[1].loglog(hm.time.mean(0), hm.data.T, 'k-')
# axs[1].loglog(hm.time.mean(0), hm.data.mean(0))

# axs[2].loglog(hm.time.mean(0), hm.data.mean(0), '.-')
# axs[2].loglog(lm.time.mean(0), lm.data.mean(0), '.-')

# # axs[1].set_ylim(3e-12, 3e-6);

# plt.show()
# %%

import plotly.graph_objects as go

fig = go.Figure()

# Low mass data
for data in lm.data.T:
    fig.add_trace(go.Scatter(x=lm.time.mean(0), y=data, mode='lines', line=dict(color='black'), showlegend=False))
fig.add_trace(go.Scatter(x=lm.time.mean(0), y=lm.data.mean(0), mode='lines', name='Low Mass Mean'))

# High mass data
for data in hm.data.T:
    fig.add_trace(go.Scatter(x=hm.time.mean(0), y=data, mode='lines', line=dict(color='black'), showlegend=False))
fig.add_trace(go.Scatter(x=hm.time.mean(0), y=hm.data.mean(0), mode='lines', name='High Mass Mean'))

# Combined data
fig.add_trace(go.Scatter(x=hm.time.mean(0), y=hm.data.mean(0), mode='lines+markers', name='High Mass Mean Combined'))
fig.add_trace(go.Scatter(x=lm.time.mean(0), y=lm.data.mean(0), mode='lines+markers', name='Low Mass Mean Combined'))

fig.update_layout(
    xaxis_type="log",
    yaxis_type="log",
    title="USF Data",
    xaxis_title="Time",
    yaxis_title="Data",
    template="plotly_white"
)

fig.show()
# %%

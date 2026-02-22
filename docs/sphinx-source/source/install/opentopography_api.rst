DEM: OpenTopography API Key Application
==================================

This page explains how to request an OpenTopography API key and what to capture in screenshots. After you receive the key, you can configure your application to access OpenTopography services.

Application link
----------------

- Main portal: https://opentopography.org/

Recommended email (education)
-----------------------------

Use an academic/education email address whenever possible. Academic users receive higher daily rate limits and can request access to academic-only datasets.

Steps (with screenshot guidance)
-------------------------------

#. Open the portal and create an account (or sign in).
#. Navigate to your dashboard and open the **API** / **API Keys** section.
#. Click **Create API Key** or **Request API Key**.
#. Fill in the intended use (research/teaching/education). Use your academic email if available.
#. Accept the Terms of Use / Data Use Policy and submit the request.
#. If the key is issued immediately, copy it from the confirmation page. If approval is required, check your email.
#. Store the key securely and keep it private.

Suggested screenshots to capture
-------------------------------

- The portal homepage showing the login/register entry.

	.. figure:: ../assets/open_topo_homepage.png
		 :alt: OpenTopography homepage
		 :width: 90%

		 Homepage with login/register entry.

- The user dashboard where **API** / **API Keys** is visible.

	.. figure:: ../assets/developers_api_apply.png
		 :alt: Developers API apply entry
		 :width: 90%

		 Dashboard entry for API key application.

- The **Create API Key** form with the usage description field.

	.. figure:: ../assets/apply_account.png
		 :alt: API key application form
		 :width: 90%

		 Application form with intended use and email.

- The confirmation page that shows the newly issued API key (mask the key after saving it).

	.. figure:: ../assets/generate_api_key.png
		 :alt: Generated API key confirmation
		 :width: 90%

		 Confirmation page showing the generated API key.

Education/academic API key advantages
-------------------------------------

Based on OpenTopography’s published notes:

- **Higher daily rate limits** for academic users.
	- Global Datasets API: 500 calls per 24 hours for academics vs 100 for non-academics.
	- USGS 3DEP Raster API: 300 calls per 24 hours for academics vs 100 for non-academics.
- **Access to academic-only data**: USGS 3DEP 1m DEM is restricted to academic users and can be requested through the OpenTopography portal.
- **Large coverage allowances** for specific datasets (request area limits apply by dataset and resolution).

API overview (for context)
--------------------------

OpenTopography provides multiple services, including:

- **Global Datasets API** (SRTM, ALOS, NASADEM, Copernicus, GEBCO, GEDI, etc.).
- **USGS 3DEP Raster API** (1m, 10m, 30m DEM).
- **Data Catalog API** (bounding-box search).
- **STAC Catalog** for hosted raster DEM metadata.
- **CSW Catalog Service** endpoints (OGC CSW 2.0.2) with sample operations such as GetCapabilities and GetRecordById.

Notes
-----

- API keys are required and must not be shared or embedded in public applications.
- If your key is compromised, revoke it and create a new one in the dashboard.

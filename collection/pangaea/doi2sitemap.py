# Sample text containing DOI URLs
text = """
Zhang, B; Tian, H; Lu, C et al. (2017): Manure nitrogen production and application in cropland and rangeland during 1860 - 2014: A 5-minute gridded global data set for Earth system modeling
Supplement to: Zhang, B; Tian, H; Lu, C et al. (2017): Global manure nitrogen production and application in cropland during 1860-2014: a 5 arcmin gridded global dataset for Earth system modeling. Earth System Science Data
Size: 10 data points
https://doi.org/10.1594/PANGAEA.871980 – Score: 180.85
Bian, Z; Tian, H; Yang, Q et al. (2020): Gridded datasets of animal manure nitrogen and phosphorus production and application in the continental U.S. from 1860 to 2017
Size: 24 data points
https://doi.org/10.1594/PANGAEA.919937 – Score: 144.19
Xu, R; Tian, H; Pan, S et al. (2018): Half-degree gridded manure and fertilizer nitrogen inputs in global grassland systems during 1860-2016
Supplement to: Xu, R; Tian, H; Pan, S et al. (2019): Increased nitrogen enrichment and shifted patterns in the world's grassland: 1860-2014. Earth System Science Data
Size: 12 data points
https://doi.org/10.1594/PANGAEA.892940 – Score: 136.2
Langeveld, J; Bouwman, AF; van Hoek, WJ et al. (2020): Global database on dissolved carbon in soil solution, including ancillary information on a range of potential drivers
Size: 7.8 MBytes
https://doi.org/10.1594/PANGAEA.911161 – Score: 12.61
"""

# Extract DOI URLs from the text
import re
doi_urls = re.findall(r"https://doi.org/\S+", text)

# Create the sitemap.xml content
sitemap_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for doi_url in doi_urls:
    sitemap_content += f'  <url>\n    <loc>{doi_url}</loc>\n  </url>\n'

sitemap_content += '</urlset>'

# Save the sitemap.xml file
with open("sitemap.xml", "w") as sitemap_file:
    sitemap_file.write(sitemap_content)

print("Sitemap.xml file created with DOI URLs.")


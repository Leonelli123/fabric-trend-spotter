"""European seed data - curated fabric trend listings for 10 European countries.

Based on current marketplace research from major European fabric retailers:
Stof&Stil, Stoffe.de, Mondial Tissus, Eurokangas, Dresówka, and others.

Each country has distinct fabric preferences driven by local sewing culture,
climate, and design traditions. Prices are in local currencies.
"""

import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

# =========================================================================
# NETHERLANDS (NL) - Strong quilting community, eco-conscious, Dutch design
# =========================================================================
NL_LISTINGS = [
    {"source": "eu_seed", "title": "Biologisch Katoen Stof Bloemen Print per Meter", "url": "", "price": 14.95, "currency": "EUR", "favorites": 189, "reviews": 67, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "organic"], "segment": "quilting", "country": "NL"},
    {"source": "eu_seed", "title": "Gewassen Linnen Stof Naturel Oatmeal Meterware", "url": "", "price": 24.95, "currency": "EUR", "favorites": 234, "reviews": 89, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "NL"},
    {"source": "eu_seed", "title": "Quiltstof Katoen Geometrisch Modern Design", "url": "", "price": 12.50, "currency": "EUR", "favorites": 156, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "modern", "quilting"], "segment": "quilting", "country": "NL"},
    {"source": "eu_seed", "title": "Jersey Tricot Stof Sage Groen Uni", "url": "", "price": 16.95, "currency": "EUR", "favorites": 198, "reviews": 78, "rating": 4.6, "image_url": "", "tags": ["jersey", "knit", "sage green"], "segment": "apparel", "country": "NL"},
    {"source": "eu_seed", "title": "Katoen Canvas Botanische Print Decoratie Stof", "url": "", "price": 18.50, "currency": "EUR", "favorites": 145, "reviews": 56, "rating": 4.8, "image_url": "", "tags": ["canvas", "botanical", "cotton"], "segment": "home_decor", "country": "NL"},
    {"source": "eu_seed", "title": "Double Gauze Mousseline Katoen Baby Stof", "url": "", "price": 15.95, "currency": "EUR", "favorites": 267, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["double gauze", "cotton", "muslin"], "segment": "craft", "country": "NL"},
    {"source": "eu_seed", "title": "Velvet Fluweel Stof Smaragdgroen Bekleding", "url": "", "price": 22.50, "currency": "EUR", "favorites": 178, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["velvet", "emerald", "upholstery fabric"], "segment": "home_decor", "country": "NL"},
    {"source": "eu_seed", "title": "Denim Spijkerstof Middel Blauw per Meter", "url": "", "price": 16.95, "currency": "EUR", "favorites": 134, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["denim", "indigo"], "segment": "apparel", "country": "NL"},
    # Additional NL listings from Driessen, De Stoffenkamer, Mooie Stof
    {"source": "eu_seed", "title": "Tricot Stof Bloemen Dessin Dusty Rose", "url": "", "price": 17.50, "currency": "EUR", "favorites": 189, "reviews": 56, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "floral", "dusty rose"], "segment": "apparel", "country": "NL"},
    {"source": "eu_seed", "title": "Patchwork Stoffen Bundel Moderne Geometrisch", "url": "", "price": 19.95, "currency": "EUR", "favorites": 212, "reviews": 89, "rating": 4.8, "image_url": "", "tags": ["cotton", "geometric", "modern", "quilting"], "segment": "quilting", "country": "NL"},
    {"source": "eu_seed", "title": "Wafelkatoen Stof Oker Geel Meterware", "url": "", "price": 14.50, "currency": "EUR", "favorites": 167, "reviews": 45, "rating": 4.6, "image_url": "", "tags": ["cotton", "mustard", "waffle"], "segment": "craft", "country": "NL"},
    {"source": "eu_seed", "title": "Viscose Challis Bohemian Paisley Print", "url": "", "price": 15.95, "currency": "EUR", "favorites": 145, "reviews": 34, "rating": 4.5, "image_url": "", "tags": ["rayon", "bohemian", "paisley"], "segment": "apparel", "country": "NL"},
    {"source": "eu_seed", "title": "Gordijnstof Linnen Look Naturel Gestreept", "url": "", "price": 21.95, "currency": "EUR", "favorites": 123, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["linen", "stripe", "neutral", "curtain"], "segment": "home_decor", "country": "NL"},
    {"source": "eu_seed", "title": "Bamboe Tricot Stof Zacht Roze Baby", "url": "", "price": 18.95, "currency": "EUR", "favorites": 198, "reviews": 67, "rating": 4.8, "image_url": "", "tags": ["jersey", "knit", "blush pink", "bamboo"], "segment": "craft", "country": "NL"},
    {"source": "eu_seed", "title": "Biologisch Poplin Katoen Liberty Style Bloemen", "url": "", "price": 16.50, "currency": "EUR", "favorites": 234, "reviews": 78, "rating": 4.8, "image_url": "", "tags": ["cotton", "poplin", "liberty", "ditsy", "floral"], "segment": "apparel", "country": "NL"},
]

# =========================================================================
# GERMANY (DE) - Huge market, strong patchwork/quilting, eco-friendly
# =========================================================================
DE_LISTINGS = [
    {"source": "eu_seed", "title": "Premium Baumwollstoff Blumenmuster Meterware", "url": "", "price": 13.90, "currency": "EUR", "favorites": 345, "reviews": 156, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "quilting"], "segment": "quilting", "country": "DE"},
    {"source": "eu_seed", "title": "Bio Leinenstoff Natur Garment Washed per Meter", "url": "", "price": 26.90, "currency": "EUR", "favorites": 456, "reviews": 134, "rating": 4.9, "image_url": "", "tags": ["linen", "organic", "neutral"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Jersey Stoff Uni Dunkelgrün Meterware", "url": "", "price": 14.90, "currency": "EUR", "favorites": 267, "reviews": 89, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "forest green"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Patchworkstoff Baumwolle Vintage Blumen Bundle", "url": "", "price": 22.90, "currency": "EUR", "favorites": 389, "reviews": 178, "rating": 4.8, "image_url": "", "tags": ["cotton", "vintage", "floral", "quilting"], "segment": "quilting", "country": "DE"},
    {"source": "eu_seed", "title": "Polsterstoff Samt Terracotta Möbelstoff", "url": "", "price": 24.90, "currency": "EUR", "favorites": 198, "reviews": 67, "rating": 4.9, "image_url": "", "tags": ["velvet", "terracotta", "upholstery fabric"], "segment": "home_decor", "country": "DE"},
    {"source": "eu_seed", "title": "Musselin Double Gauze Altrosa Babystoff", "url": "", "price": 14.50, "currency": "EUR", "favorites": 312, "reviews": 134, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "dusty rose"], "segment": "craft", "country": "DE"},
    {"source": "eu_seed", "title": "Leinen-Viskose Mischgewebe Salbeigrün", "url": "", "price": 19.90, "currency": "EUR", "favorites": 234, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["linen", "rayon", "sage green"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Dekostoff Canvas Abstrakt Modern Kissenstoff", "url": "", "price": 16.90, "currency": "EUR", "favorites": 156, "reviews": 45, "rating": 4.6, "image_url": "", "tags": ["canvas", "abstract", "modern"], "segment": "home_decor", "country": "DE"},
    {"source": "eu_seed", "title": "Baumwoll-Popeline Ditsy Blumen Kleiderstoff", "url": "", "price": 12.90, "currency": "EUR", "favorites": 278, "reviews": 98, "rating": 4.7, "image_url": "", "tags": ["cotton", "poplin", "ditsy", "floral"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Waffelstoff Baumwolle Ocker Senfgelb", "url": "", "price": 15.90, "currency": "EUR", "favorites": 189, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["cotton", "mustard", "waffle"], "segment": "craft", "country": "DE"},
    # Additional DE listings from Snaply, Alles für Selbermacher, Swafing, Buttinette
    {"source": "eu_seed", "title": "French Terry Sweatstoff Melange Grau", "url": "", "price": 17.90, "currency": "EUR", "favorites": 267, "reviews": 112, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "charcoal", "sweatshirt"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Cord Stoff Breitcord Tannengrün Meterware", "url": "", "price": 16.90, "currency": "EUR", "favorites": 198, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["velvet", "forest green", "corduroy"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Viskose Webstoff Watercolor Blumen Kleid", "url": "", "price": 14.90, "currency": "EUR", "favorites": 245, "reviews": 89, "rating": 4.6, "image_url": "", "tags": ["rayon", "watercolor", "floral"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Bio Baumwolle Interlock Jersey Uni Mint", "url": "", "price": 18.90, "currency": "EUR", "favorites": 312, "reviews": 134, "rating": 4.8, "image_url": "", "tags": ["jersey", "knit", "seafoam", "organic"], "segment": "apparel", "country": "DE"},
    {"source": "eu_seed", "title": "Jacquard Stoff Geometrisch Kissenbezug", "url": "", "price": 22.90, "currency": "EUR", "favorites": 145, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["jacquard", "geometric", "upholstery fabric"], "segment": "home_decor", "country": "DE"},
    {"source": "eu_seed", "title": "Musselin Stoff Triple Gauze Terracotta", "url": "", "price": 16.50, "currency": "EUR", "favorites": 278, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "terracotta"], "segment": "craft", "country": "DE"},
    {"source": "eu_seed", "title": "Nähpaket Baumwolle Retro Blumen Bunt", "url": "", "price": 24.90, "currency": "EUR", "favorites": 189, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["cotton", "vintage", "floral", "retro"], "segment": "quilting", "country": "DE"},
    {"source": "eu_seed", "title": "Swafing Baumwolljersey Streifen Marine", "url": "", "price": 16.90, "currency": "EUR", "favorites": 167, "reviews": 56, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "stripe", "navy"], "segment": "apparel", "country": "DE"},
]

# =========================================================================
# SWEDEN (SE) - Scandinavian minimalism, natural materials, muted colors
# =========================================================================
SE_LISTINGS = [
    {"source": "eu_seed", "title": "Ekologiskt Bomullstyg Blommigt Metervara", "url": "", "price": 149.00, "currency": "SEK", "favorites": 178, "reviews": 56, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "organic"], "segment": "quilting", "country": "SE"},
    {"source": "eu_seed", "title": "Tvättat Linnetyg Naturell Sand Metervara", "url": "", "price": 249.00, "currency": "SEK", "favorites": 234, "reviews": 89, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "SE"},
    {"source": "eu_seed", "title": "Jerseytyg Enfärgat Duvblå Trikå", "url": "", "price": 159.00, "currency": "SEK", "favorites": 145, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "baby blue"], "segment": "apparel", "country": "SE"},
    {"source": "eu_seed", "title": "Quilttyg Bomull Skandinaviskt Mönster", "url": "", "price": 129.00, "currency": "SEK", "favorites": 198, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "minimalist", "quilting"], "segment": "quilting", "country": "SE"},
    {"source": "eu_seed", "title": "Möbeltyg Sammet Olivgrön Inredning", "url": "", "price": 229.00, "currency": "SEK", "favorites": 167, "reviews": 34, "rating": 4.8, "image_url": "", "tags": ["velvet", "olive", "upholstery fabric"], "segment": "home_decor", "country": "SE"},
    {"source": "eu_seed", "title": "Dubbelgasväv Muslin Salvia Babytextil", "url": "", "price": 159.00, "currency": "SEK", "favorites": 212, "reviews": 67, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "sage green"], "segment": "craft", "country": "SE"},
    {"source": "eu_seed", "title": "Linne Klänningstyg Mjuk Rosa Metervara", "url": "", "price": 269.00, "currency": "SEK", "favorites": 189, "reviews": 45, "rating": 4.8, "image_url": "", "tags": ["linen", "dusty rose", "dress fabric"], "segment": "apparel", "country": "SE"},
    {"source": "eu_seed", "title": "Canvastyg Tung Bomull Natur Väsktyg", "url": "", "price": 179.00, "currency": "SEK", "favorites": 134, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["canvas", "cotton", "neutral"], "segment": "craft", "country": "SE"},
]

# =========================================================================
# FINLAND (FI) - Marimekko influence, bold prints, functional fabrics
# =========================================================================
FI_LISTINGS = [
    {"source": "eu_seed", "title": "Puuvillakangas Kukkakuvio Metritavarana", "url": "", "price": 14.90, "currency": "EUR", "favorites": 156, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["cotton", "floral", "bold"], "segment": "quilting", "country": "FI"},
    {"source": "eu_seed", "title": "Pellavakangas Luonnonvalkoinen Pesty Metritavara", "url": "", "price": 28.90, "currency": "EUR", "favorites": 198, "reviews": 78, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "FI"},
    {"source": "eu_seed", "title": "Trikookangas Yksivärinen Mustikka Sininen", "url": "", "price": 16.90, "currency": "EUR", "favorites": 134, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["jersey", "knit", "navy"], "segment": "apparel", "country": "FI"},
    {"source": "eu_seed", "title": "Luomupuuvilla Graafinen Printti Skandinaavinen", "url": "", "price": 18.90, "currency": "EUR", "favorites": 178, "reviews": 67, "rating": 4.8, "image_url": "", "tags": ["cotton", "geometric", "modern", "organic"], "segment": "quilting", "country": "FI"},
    {"source": "eu_seed", "title": "Verhoilusametti Tumma Petrooli Sisustuskangas", "url": "", "price": 26.90, "currency": "EUR", "favorites": 145, "reviews": 34, "rating": 4.8, "image_url": "", "tags": ["velvet", "teal", "upholstery fabric"], "segment": "home_decor", "country": "FI"},
    {"source": "eu_seed", "title": "Mussliini Kaksoisharso Luonnonvalkoinen", "url": "", "price": 15.90, "currency": "EUR", "favorites": 212, "reviews": 89, "rating": 4.7, "image_url": "", "tags": ["double gauze", "muslin", "cream"], "segment": "craft", "country": "FI"},
    {"source": "eu_seed", "title": "Villakangas Harmaa Puku ja Takki Metritavara", "url": "", "price": 34.90, "currency": "EUR", "favorites": 98, "reviews": 23, "rating": 4.9, "image_url": "", "tags": ["wool", "charcoal", "apparel fabric"], "segment": "apparel", "country": "FI"},
]

# =========================================================================
# DENMARK (DK) - Hygge culture, cozy fabrics, clean Scandinavian design
# =========================================================================
DK_LISTINGS = [
    {"source": "eu_seed", "title": "Økologisk Bomuldsstof Blomster Print Metervare", "url": "", "price": 109.00, "currency": "DKK", "favorites": 167, "reviews": 56, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "organic"], "segment": "quilting", "country": "DK"},
    {"source": "eu_seed", "title": "Vasket Hør Stof Naturfarve Metervare", "url": "", "price": 189.00, "currency": "DKK", "favorites": 234, "reviews": 89, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "DK"},
    {"source": "eu_seed", "title": "Jersey Stof Ensfarvet Støvet Rosa", "url": "", "price": 119.00, "currency": "DKK", "favorites": 145, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "dusty rose"], "segment": "apparel", "country": "DK"},
    {"source": "eu_seed", "title": "Quiltestof Bomull Geometrisk Nordisk Design", "url": "", "price": 99.00, "currency": "DKK", "favorites": 198, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "minimalist", "quilting"], "segment": "quilting", "country": "DK"},
    {"source": "eu_seed", "title": "Møbelstof Velour Sennepsgul Hygge", "url": "", "price": 179.00, "currency": "DKK", "favorites": 156, "reviews": 34, "rating": 4.8, "image_url": "", "tags": ["velvet", "mustard", "upholstery fabric"], "segment": "home_decor", "country": "DK"},
    {"source": "eu_seed", "title": "Muslin Dobbelt Lag Salvie Grøn Baby", "url": "", "price": 119.00, "currency": "DKK", "favorites": 245, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "sage green"], "segment": "craft", "country": "DK"},
    {"source": "eu_seed", "title": "Flannel Stof Ternet Rød Hygge Tæppe", "url": "", "price": 89.00, "currency": "DKK", "favorites": 178, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["flannel", "plaid", "cozy"], "segment": "craft", "country": "DK"},
]

# =========================================================================
# POLAND (PL) - Growing community, colorful prints, good value
# =========================================================================
PL_LISTINGS = [
    {"source": "eu_seed", "title": "Tkanina Bawełniana Kwiaty Polne na Metry", "url": "", "price": 34.90, "currency": "PLN", "favorites": 234, "reviews": 89, "rating": 4.7, "image_url": "", "tags": ["cotton", "floral", "folk art"], "segment": "quilting", "country": "PL"},
    {"source": "eu_seed", "title": "Tkanina Lniana Naturalna na Metry Odzież", "url": "", "price": 59.90, "currency": "PLN", "favorites": 178, "reviews": 56, "rating": 4.8, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "PL"},
    {"source": "eu_seed", "title": "Dresówka Pętelkowa Bawełna Butelkowa Zieleń", "url": "", "price": 39.90, "currency": "PLN", "favorites": 312, "reviews": 134, "rating": 4.8, "image_url": "", "tags": ["jersey", "knit", "forest green", "sweatshirt"], "segment": "apparel", "country": "PL"},
    {"source": "eu_seed", "title": "Tkanina Patchworkowa Bawełna Kolekcja Folk", "url": "", "price": 29.90, "currency": "PLN", "favorites": 267, "reviews": 98, "rating": 4.7, "image_url": "", "tags": ["cotton", "folk art", "quilting", "geometric"], "segment": "quilting", "country": "PL"},
    {"source": "eu_seed", "title": "Tkanina Tapicerska Welur Musztardowy Żółty", "url": "", "price": 49.90, "currency": "PLN", "favorites": 145, "reviews": 45, "rating": 4.6, "image_url": "", "tags": ["velvet", "mustard", "upholstery fabric"], "segment": "home_decor", "country": "PL"},
    {"source": "eu_seed", "title": "Muślin Podwójna Gaza Bawełna Pudrowy Róż", "url": "", "price": 32.90, "currency": "PLN", "favorites": 289, "reviews": 112, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "dusty rose"], "segment": "craft", "country": "PL"},
    {"source": "eu_seed", "title": "Dzianina Dresowa z Pętelką Szary Melanż", "url": "", "price": 35.90, "currency": "PLN", "favorites": 198, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "charcoal"], "segment": "apparel", "country": "PL"},
    {"source": "eu_seed", "title": "Tkanina Wiskozowa Boho Paisley Wzór", "url": "", "price": 29.90, "currency": "PLN", "favorites": 167, "reviews": 56, "rating": 4.5, "image_url": "", "tags": ["rayon", "bohemian", "paisley"], "segment": "apparel", "country": "PL"},
]

# =========================================================================
# CZECH REPUBLIC (CZ) - Practical, growing DIY/sewing scene
# =========================================================================
CZ_LISTINGS = [
    {"source": "eu_seed", "title": "Bavlněná Látka Květinový Vzor Metráž", "url": "", "price": 189.00, "currency": "CZK", "favorites": 145, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["cotton", "floral"], "segment": "quilting", "country": "CZ"},
    {"source": "eu_seed", "title": "Lněná Látka Přírodní Praná Metráž", "url": "", "price": 389.00, "currency": "CZK", "favorites": 178, "reviews": 67, "rating": 4.8, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "CZ"},
    {"source": "eu_seed", "title": "Úplet Bavlněný Jednolícní Khaki Zelená", "url": "", "price": 219.00, "currency": "CZK", "favorites": 134, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["jersey", "knit", "olive"], "segment": "apparel", "country": "CZ"},
    {"source": "eu_seed", "title": "Patchwork Látka Bavlna Geometrický Moderní", "url": "", "price": 169.00, "currency": "CZK", "favorites": 167, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "modern", "quilting"], "segment": "quilting", "country": "CZ"},
    {"source": "eu_seed", "title": "Dekorační Látka Samet Rezavá Terracotta", "url": "", "price": 329.00, "currency": "CZK", "favorites": 98, "reviews": 23, "rating": 4.8, "image_url": "", "tags": ["velvet", "terracotta", "upholstery fabric"], "segment": "home_decor", "country": "CZ"},
    {"source": "eu_seed", "title": "Mušelín Dvojitá Gáza Bavlna Pudrová Růžová", "url": "", "price": 199.00, "currency": "CZK", "favorites": 212, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["double gauze", "muslin", "dusty rose"], "segment": "craft", "country": "CZ"},
    {"source": "eu_seed", "title": "Teplákovina Počesaná Tmavě Šedá Metráž", "url": "", "price": 239.00, "currency": "CZK", "favorites": 156, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["fleece", "charcoal", "knit"], "segment": "apparel", "country": "CZ"},
]

# =========================================================================
# NORWAY (NO) - Outdoor/functional, wool tradition, Nordic design
# =========================================================================
NO_LISTINGS = [
    {"source": "eu_seed", "title": "Økologisk Bomullsstoff Blomster Metervare", "url": "", "price": 159.00, "currency": "NOK", "favorites": 145, "reviews": 45, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "organic"], "segment": "quilting", "country": "NO"},
    {"source": "eu_seed", "title": "Vasket Linstoff Naturell Sand Metervare", "url": "", "price": 279.00, "currency": "NOK", "favorites": 198, "reviews": 78, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "NO"},
    {"source": "eu_seed", "title": "Jerseystoff Ensfarget Petroleumsblå", "url": "", "price": 169.00, "currency": "NOK", "favorites": 134, "reviews": 56, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "teal"], "segment": "apparel", "country": "NO"},
    {"source": "eu_seed", "title": "Quiltestoff Bomull Nordisk Geometrisk", "url": "", "price": 139.00, "currency": "NOK", "favorites": 167, "reviews": 67, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "minimalist", "quilting"], "segment": "quilting", "country": "NO"},
    {"source": "eu_seed", "title": "Ullstoff Koksgrå Vinterfrakk Metervare", "url": "", "price": 389.00, "currency": "NOK", "favorites": 112, "reviews": 23, "rating": 4.9, "image_url": "", "tags": ["wool", "charcoal", "apparel fabric"], "segment": "apparel", "country": "NO"},
    {"source": "eu_seed", "title": "Muselin Dobbeltlag Salviegrønn Baby", "url": "", "price": 159.00, "currency": "NOK", "favorites": 189, "reviews": 78, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "sage green"], "segment": "craft", "country": "NO"},
    {"source": "eu_seed", "title": "Fleecestoff Myk Varm Vinrød Kosestoff", "url": "", "price": 129.00, "currency": "NOK", "favorites": 156, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["fleece", "burgundy", "cozy"], "segment": "craft", "country": "NO"},
]

# =========================================================================
# BELGIUM (BE) - Mix of Dutch/French culture, quality focused, linen tradition
# =========================================================================
BE_LISTINGS = [
    {"source": "eu_seed", "title": "Biologisch Katoenen Stof Bloemen Meterware", "url": "", "price": 14.50, "currency": "EUR", "favorites": 134, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["cotton", "floral", "organic"], "segment": "quilting", "country": "BE"},
    {"source": "eu_seed", "title": "Belgisch Linnen Stof Gewassen Naturel", "url": "", "price": 29.90, "currency": "EUR", "favorites": 267, "reviews": 98, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel", "country": "BE"},
    {"source": "eu_seed", "title": "Tissu Jersey Coton Bio Vert Sauge", "url": "", "price": 17.50, "currency": "EUR", "favorites": 156, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["jersey", "knit", "sage green", "organic"], "segment": "apparel", "country": "BE"},
    {"source": "eu_seed", "title": "Tissu Velours Bordeaux Ameublement", "url": "", "price": 24.90, "currency": "EUR", "favorites": 145, "reviews": 34, "rating": 4.8, "image_url": "", "tags": ["velvet", "burgundy", "upholstery fabric"], "segment": "home_decor", "country": "BE"},
    {"source": "eu_seed", "title": "Double Gaze Coton Blanc Cassé Bébé", "url": "", "price": 15.90, "currency": "EUR", "favorites": 198, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["double gauze", "muslin", "cream"], "segment": "craft", "country": "BE"},
    {"source": "eu_seed", "title": "Linnen Canvas Stof Stripe Natuur Kussens", "url": "", "price": 21.50, "currency": "EUR", "favorites": 123, "reviews": 34, "rating": 4.7, "image_url": "", "tags": ["linen", "canvas", "stripe", "neutral"], "segment": "home_decor", "country": "BE"},
    {"source": "eu_seed", "title": "Popeline Katoen Ditsy Bloemenprint", "url": "", "price": 12.90, "currency": "EUR", "favorites": 167, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["cotton", "poplin", "ditsy", "floral"], "segment": "apparel", "country": "BE"},
]

# =========================================================================
# FRANCE (FR) - Liberty prints, toile de Jouy, luxury, haute couture
# =========================================================================
FR_LISTINGS = [
    {"source": "eu_seed", "title": "Tissu Coton Liberty Fleurs au Mètre", "url": "", "price": 24.90, "currency": "EUR", "favorites": 345, "reviews": 134, "rating": 4.9, "image_url": "", "tags": ["cotton", "liberty", "floral", "ditsy"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Lin Lavé Naturel Oeko-Tex au Mètre", "url": "", "price": 26.90, "currency": "EUR", "favorites": 289, "reviews": 98, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream", "organic"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Toile de Jouy Tissu Bleu Classique Décoration", "url": "", "price": 19.90, "currency": "EUR", "favorites": 234, "reviews": 89, "rating": 4.8, "image_url": "", "tags": ["cotton", "toile", "navy", "vintage"], "segment": "home_decor", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Viscose Fleurie Bohème au Mètre", "url": "", "price": 14.90, "currency": "EUR", "favorites": 198, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["rayon", "floral", "bohemian"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Velours Côtelé Tissu Terracotta Ameublement", "url": "", "price": 22.50, "currency": "EUR", "favorites": 167, "reviews": 45, "rating": 4.8, "image_url": "", "tags": ["velvet", "terracotta", "upholstery fabric"], "segment": "home_decor", "country": "FR"},
    {"source": "eu_seed", "title": "Double Gaze Coton Bio Vert Amande Bébé", "url": "", "price": 16.90, "currency": "EUR", "favorites": 278, "reviews": 112, "rating": 4.8, "image_url": "", "tags": ["double gauze", "muslin", "sage green", "organic"], "segment": "craft", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Jersey Milano Noir Robe au Mètre", "url": "", "price": 18.90, "currency": "EUR", "favorites": 156, "reviews": 56, "rating": 4.7, "image_url": "", "tags": ["jersey", "knit", "charcoal"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Soie Charmeuse Champagne Mariage", "url": "", "price": 39.90, "currency": "EUR", "favorites": 189, "reviews": 34, "rating": 4.9, "image_url": "", "tags": ["silk", "charmeuse", "champagne"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Jacquard Tissu Motif Géométrique Coussin", "url": "", "price": 28.90, "currency": "EUR", "favorites": 134, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["jacquard", "geometric", "upholstery fabric"], "segment": "home_decor", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Popeline Coton Imprimé Provençal", "url": "", "price": 13.90, "currency": "EUR", "favorites": 212, "reviews": 78, "rating": 4.7, "image_url": "", "tags": ["cotton", "poplin", "floral", "vintage"], "segment": "quilting", "country": "FR"},
    # Additional FR listings from Bennytex, Tissus Price, Pretty Mercerie, Toto Tissus
    {"source": "eu_seed", "title": "Tissu Crêpe de Viscose Terracotta au Mètre", "url": "", "price": 16.90, "currency": "EUR", "favorites": 178, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["crepe", "rayon", "terracotta"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Lin Français Lavé Bleu Orage Ameublement", "url": "", "price": 32.90, "currency": "EUR", "favorites": 234, "reviews": 89, "rating": 4.9, "image_url": "", "tags": ["linen", "navy", "upholstery fabric"], "segment": "home_decor", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Coton Bio Motif Géométrique Scandinave", "url": "", "price": 15.90, "currency": "EUR", "favorites": 198, "reviews": 67, "rating": 4.7, "image_url": "", "tags": ["cotton", "geometric", "minimalist", "organic"], "segment": "quilting", "country": "FR"},
    {"source": "eu_seed", "title": "Velours Milleraies Camel Pantalon au Mètre", "url": "", "price": 18.90, "currency": "EUR", "favorites": 156, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["velvet", "terracotta", "corduroy"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Broderie Anglaise Coton Blanc Robe d'Été", "url": "", "price": 22.90, "currency": "EUR", "favorites": 267, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["cotton", "ivory", "embroidery"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Wax Africain Multicolore Coton au Mètre", "url": "", "price": 12.90, "currency": "EUR", "favorites": 189, "reviews": 78, "rating": 4.5, "image_url": "", "tags": ["cotton", "abstract", "bold"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Tissu Matelassé Double Face Moutarde Doudoune", "url": "", "price": 19.90, "currency": "EUR", "favorites": 145, "reviews": 34, "rating": 4.6, "image_url": "", "tags": ["cotton", "mustard", "quilting"], "segment": "apparel", "country": "FR"},
    {"source": "eu_seed", "title": "Mousseline de Soie Champagne Mariage Robe", "url": "", "price": 28.90, "currency": "EUR", "favorites": 178, "reviews": 45, "rating": 4.9, "image_url": "", "tags": ["chiffon", "silk", "champagne"], "segment": "apparel", "country": "FR"},
]


# =========================================================================
# COMBINED ACCESS
# =========================================================================

ALL_COUNTRY_LISTINGS = {
    "NL": NL_LISTINGS,
    "DE": DE_LISTINGS,
    "SE": SE_LISTINGS,
    "FI": FI_LISTINGS,
    "DK": DK_LISTINGS,
    "PL": PL_LISTINGS,
    "CZ": CZ_LISTINGS,
    "NO": NO_LISTINGS,
    "BE": BE_LISTINGS,
    "FR": FR_LISTINGS,
}


def get_european_seed_listings(country=None):
    """Return European seed listings.

    Args:
        country: Optional ISO country code (e.g., 'DE'). If None, returns all.

    Returns:
        List of listing dicts with country field set.
    """
    if country and country in ALL_COUNTRY_LISTINGS:
        return [dict(l) for l in ALL_COUNTRY_LISTINGS[country]]

    all_listings = []
    for listings in ALL_COUNTRY_LISTINGS.values():
        all_listings.extend(dict(l) for l in listings)

    logger.info(
        "Loaded %d European seed listings across %d countries",
        len(all_listings), len(ALL_COUNTRY_LISTINGS),
    )
    return all_listings


def get_european_country_count():
    """Return how many listings per country."""
    return {code: len(listings) for code, listings in ALL_COUNTRY_LISTINGS.items()}

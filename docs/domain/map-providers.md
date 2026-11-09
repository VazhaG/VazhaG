---
id: map-providers
type: domain
title: რუკის წყაროები — Google-ის მსგავსი იერისთვის
status: living
updated: 2026-11-09
related:
  - "[[ADR-0013-vector-map-openfreemap]]"
  - "[[map-tile-colours]]"
---

# რუკის წყაროები — Google-ის მსგავსი იერისთვის

მფლობელს 2026-11-09-ს დღევანდელი რუკის მწვანე ფერი არ მოეწონა და Google Maps-ის მსგავსი იერი ითხოვა. აქ წერია, რა წყაროები შემოწმდა და რა ითქვა მათ ოფიციალურ გვერდებზე. ყოველი ფაქტი თავისი წყაროთი და თარიღითაა; სანამ მასზე რამე აშენდება, ხელახლა შემოწმდეს.

## OpenFreeMap (ვექტორული რუკა) — წაკითხულია 2026-11-09

- უფასოა, ლიმიტის გარეშე: „Using our public instance is completely free: there are no limits on the number of map views or requests.“ (https://openfreemap.org/)
- რეგისტრაცია, გასაღები და cookie არ სჭირდება: „There's no registration, no user database, no API keys, and no cookies.“ (https://openfreemap.org/)
- კომერციული გამოყენება — „Yes.“ (https://openfreemap.org/, „Is commercial usage allowed?“)
- ატრიბუცია სავალდებულოა; MapLibre-ით ის თავისით ემატება (https://openfreemap.org/).
- გარანტია არ არის: „At the moment, I don't offer SLA guarantees or personalized support.“ (https://openfreemap.org/); მომსახურება „as-is“-ია და შეიძლება „discontinue it at any time without notice“ (https://openfreemap.org/tos/, განახლებულია 2026-10-14).
- პირობები: საჯარო მომსახურების საიტში ჩასმისთვის ინტეგრატორი მინიმუმ 18 წლის უნდა იყოს; მოქმედებს უნგრეთის კანონი; ავტომატური მასობრივი ჩამოტვირთვა აკრძალულია (გარდა მცირე ოფლაინ ჩამოტვირთვისა) (https://openfreemap.org/tos/).
- პროექტის ლიცენზია — MIT (https://openfreemap.org/).
- სტილები, რომლებიც მფლობელმა ნახა (2026-11-09, თბილისი, მე-13 დონე): „liberty“ (ნაცრისფერი კვარტლები, ყვითელი გზები, ცისფერი წყალი, ფერმკრთალი მწვანე პარკები — ყველაზე ახლოსაა Google-თან), „positron“ (ნაცრისფერი), „dark“ (მუქი). ქართული წარწერები („თბილისი“) იხატება. მისამართი: `https://tiles.openfreemap.org/styles/<სტილი>`.

## MapLibre GL JS (ვექტორული რუკის ხატვის ბიბლიოთეკა) — წაკითხულია 2026-11-09

- ლიცენზია — BSD-3-Clause (npm-ის რეესტრი, `maplibre-gl` — 4.7.1, 5.24.0, 6.17.0; LICENSE.txt-ის ტექსტი სამპუნქტიან BSD-ს ემთხვევა, github.com/maplibre/maplibre-gl-js).
- ვერსიები (npm-ის რეესტრი): 6.16.0 — 2026-10-25, 6.17.0 — 2026-11-07 (უახლესი), 5.24.0 — 2026-04-23 (5-ის ბოლო).
- მე-6 ვერსია მხოლოდ ES მოდულებად ვრცელდება (`maplibre-gl.mjs`) (maplibre.org/maplibre-gl-js/docs/).
- უსაფრთხოების წესისთვის (CSP) სჭირდება `worker-src 'self'` და `img-src data: blob: 'self'`; მკაცრი წესისთვის worker-ის ფაილი საკუთარი მისამართიდან მიეთითება: `maplibregl.setWorkerUrl(…)` (maplibre.org/maplibre-gl-js/docs/, „CSP Directives“).
- ხატავს WebGL-ით — ტელეფონის ბრაუზერის გრაფიკული შესაძლებლობით (**ჰიპოთეზა**, რომ თანამედროვე ტელეფონების უმეტესობას აქვს; გადაუმოწმებელია).

## maplibre-gl-leaflet (ხიდი Leaflet-სა და MapLibre-ს შორის) — წაკითხულია 2026-11-09

- `@maplibre/maplibre-gl-leaflet` 0.1.4 (2026-08-16), ლიცენზია ISC; მუშაობს Leaflet ^1.9.3-თან და MapLibre ^2.4 / ^3.3.1 / ^4.3.2 / ^5 / ^6-თან (npm-ის რეესტრი, `peerDependencies`).
- მისი ფაილი (UMD) MapLibre-ს გლობალური სახელით (`maplibregl`) ეძებს (პაკეტის `leaflet-maplibre-gl.js`, მე-8 ხაზი) — მე-6 ვერსიასთან ამიტომ ერთი პატარა ჩამტვირთავი სჭირდება.

## რაც უარყოფილია და რატომ

- **CARTO (Voyager, Dark Matter)** — ფილები 2026-11-09-ს წარწერით „API KEY REQUIRED“ მოვიდა: გასაღები სჭირდება.
- **Esri World Street Map** — ფილები ჩამოიტვირთა (2026-11-09), მაგრამ თბილისში მე-13 დონეზე ბეჟი და ნაკლებად დეტალურია; Esri-ს გამოყენების პირობები გადამოწმებული არ არის.
- **Google Maps-ის ფილები** — გასაღები და გადახდა სჭირდება, და მათი პირობები ცალკე ფილების სხვა რუკაში ჩასმას ზღუდავს (**ჰიპოთეზა**, მოდელის ცოდნიდან — გადაუმოწმებელია).

// node icons.js outdir  (run with NODE_PATH pointing at a node_modules containing react, react-dom, react-icons, sharp)
const React = require('react'); const RDS = require('react-dom/server'); const sharp = require('sharp');
const md = require('react-icons/md'); const out = process.argv[2];
const names = ['MdSmartToy','MdMap','MdExplore','MdRoute','MdNearMe','MdViewInAr','MdCameraAlt','MdMemory','MdTouchApp','MdCable','MdWarningAmber','MdCheckCircle','MdFlag','MdBolt','MdSpeed','MdCategory','MdScience','MdTimer','MdDoNotDisturbOn','MdBatteryChargingFull','MdPrecisionManufacturing','MdDeleteOutline','MdPerson','MdFactory','MdHealthAndSafety','MdGroups','MdPublic','MdArticle','MdLightbulb','MdTrendingUp','MdPendingActions','MdTaskAlt','MdSettingsRemote','MdDeveloperBoard','MdLayers','MdHub','MdAutoAwesome','MdVisibility','MdInsights','MdRocketLaunch','MdSchool','MdCompareArrows','MdStorage','MdTune','MdSync','MdBlock','MdCleaningServices','MdGridOn','MdQueryStats','MdVerified'];
(async () => { for (const n of names) { const C = md[n]; if (!C) { console.log('missing', n); continue; }
  for (const [suffix, color] of [['w','#FFFFFF'],['n','#14284B']]) {
    const svg = RDS.renderToStaticMarkup(React.createElement(C, { size: 256, color }));
    await sharp(Buffer.from(svg)).png().toFile(`${out}/${n}_${suffix}.png`); } }
  console.log('done'); })();

import { Presentation, PresentationFile, column, panel, text, fill, hug } from '@oai/artifact-tool';
const p=Presentation.create({slideSize:{width:1920,height:1080}});
const s=p.slides.add();
s.compose(panel({name:'root',width:fill,height:fill,fill:'#F8FAFC',padding:80}, column({width:fill,height:fill,gap:20},[
 text('Panel Test',{width:fill,height:hug,style:{fontSize:64,bold:true,color:'#111827'}})
])),{frame:{left:0,top:0,width:1920,height:1080},baseUnit:8});
await (await PresentationFile.exportPptx(p)).save('output/panel-test.pptx');
console.log('done');

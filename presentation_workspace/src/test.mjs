import { Presentation, PresentationFile, column, text, fill, hug } from '@oai/artifact-tool';
const p=Presentation.create({slideSize:{width:1920,height:1080}});
const s=p.slides.add();
s.compose(column({name:'root',width:fill,height:fill,padding:80,gap:20},[
 text('Test slide',{name:'title',width:fill,height:hug,style:{fontSize:64,bold:true,color:'#111827'}}),
 text('Subtitle',{name:'subtitle',width:fill,height:hug,style:{fontSize:32,color:'#475569'}})
]),{frame:{left:0,top:0,width:1920,height:1080},baseUnit:8});
const blob=await PresentationFile.exportPptx(p);
await blob.save('output/test.pptx');
console.log('saved');

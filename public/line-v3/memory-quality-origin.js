// Attribute saved errors only when the exact quoted text has a unique writer.
// Overlapping quotations remain unknown; this does not change AI grades.
export function errorOrigin(record,error){
  const quote=error.outputQuote;
  if(record.task==='facts'){
    const matches=(record.profileConstruction?.storedFacts||[]).filter(f=>{
      const line=`分類：${f.key}｜事實：${f.value}｜證據：${f.evidence_seq}｜來源：${f.sourceStage}｜保存範圍：${f.temporal_scope}`;
      return line.includes(quote)||quote.includes(line);
    });
    const origins=new Set(matches.map(f=>f.sourceStage==='current'?'new':'retained'));
    return origins.size===1?[...origins][0]:'unknown';
  }
  if(!record.formatOk)return 'retained';
  const accepted=record.accepted||{};
  const inNew=(accepted.summary||'').includes(quote)||(accepted.profile||'').includes(quote);
  const retained=(record.judgedOutput.split('【實際累積印象】\n')[1]||'');
  const inRetained=!accepted.profile&&retained.includes(quote);
  return inNew&&inRetained?'unknown':inNew?'new':inRetained?'retained':'unknown';
}

export function errorOriginCounts(records){
  const counts={new:0,retained:0,unknown:0};
  for(const r of records)for(const error of r.quality.errors)counts[errorOrigin(r,error)]++;
  return counts;
}

const {Contract}=require('fabric-contract-api');
const {Anchors}=require('./anchors.cjs');
class SentinelAnchors extends Contract{
 constructor(){super('SentinelAnchors');}
 async Ping(ctx){return new Anchors().Ping(ctx);}
 async Anchor(ctx,text){return new Anchors().Anchor(ctx,text);}
 async GetAnchor(ctx,id){return new Anchors().GetAnchor(ctx,id);}
}
module.exports.contracts=[SentinelAnchors];

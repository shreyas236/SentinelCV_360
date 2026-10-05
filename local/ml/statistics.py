"""Measured embedding checks; anomaly scores are never presented as confidence."""
import numpy as np
from scipy.stats import ks_2samp
from sklearn.covariance import LedoitWolf
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import KMeans

def normalize(x):
    x=np.asarray(x,dtype=float)
    if x.ndim!=2 or not np.isfinite(x).all():raise ValueError('Finite embedding matrix required')
    return x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
def dataset_analysis(embeddings,reference,labels,semantic=None,ood_quantile=.99,near_threshold=.985):
    x=normalize(embeddings);r=normalize(reference)
    if len(r)<4:raise ValueError('At least four approved reference embeddings are required')
    nn=NearestNeighbors(n_neighbors=min(4,len(r))).fit(r)
    # Hold each baseline item out of its own neighbor calculation.
    baseline=nn.kneighbors(r)[0][:,1:].mean(axis=1);distances=nn.kneighbors(x)[0][:,1:].mean(axis=1)
    threshold=float(np.quantile(baseline,ood_quantile));cov=LedoitWolf().fit(r)
    md=cov.mahalanobis(x);base_md=cov.mahalanobis(r);md_threshold=float(np.quantile(base_md,ood_quantile))
    similarity=x@x.T;near=[]
    for i in range(len(x)):
        for j in range(i):
            if similarity[i,j]>=near_threshold:near.append({'a':i,'b':j,'cosine':float(similarity[i,j])})
    label_flags=[]
    if semantic is not None:
        probabilities=np.asarray(semantic,dtype=float)
        for i,(row,label) in enumerate(zip(probabilities,labels)):
            predicted=int(row.argmax())
            if label is not None and predicted!=label:label_flags.append({'index':i,'label':int(label),'predicted':predicted,'raw_score':float(row[predicted]-row[label]),'confidence':None})
    return {'near_duplicates':near,'ood':[{'index':i,'knn_distance':float(d),'mahalanobis':float(md[i]),'confidence':None} for i,d in enumerate(distances) if d>threshold and md[i]>md_threshold],
            'label_anomalies':label_flags,'thresholds':{'knn':threshold,'mahalanobis':md_threshold,'reference_quantile':ood_quantile,'cosine':near_threshold},
            'calibration':'UNAVAILABLE UNLESS A DOMAIN VALIDATION SET IS PROVIDED'}

def shift(reference,current):
    r=normalize(reference);x=normalize(current)
    if r.shape[1]!=x.shape[1] or min(len(r),len(x))<2:raise ValueError('Two compatible distributions are required')
    from scipy.spatial.distance import cdist
    all_data=np.concatenate([r,x]);dist=cdist(all_data,all_data,'sqeuclidean');positive=dist[dist>0]
    bandwidth=float(np.median(positive)) if len(positive) else 1.
    kernel=lambda a,b:np.exp(-cdist(a,b,'sqeuclidean')/(2*max(bandwidth,1e-8)))
    mmd=float(kernel(r,r).mean()+kernel(x,x).mean()-2*kernel(r,x).mean())
    ks=[ks_2samp(r[:,i],x[:,i]) for i in range(r.shape[1])]
    psi=[]
    for i in range(r.shape[1]):
        edges=np.unique(np.quantile(r[:,i],np.linspace(0,1,11)))
        if len(edges)<3:continue
        edges[0]=-np.inf;edges[-1]=np.inf
        a=np.maximum(np.histogram(r[:,i],edges)[0]/len(r),1e-6);b=np.maximum(np.histogram(x[:,i],edges)[0]/len(x),1e-6)
        psi.append(float(np.sum((b-a)*np.log(b/a))))
    return {'mmd':max(0,mmd),'kernel_bandwidth':bandwidth,'mean_psi':float(np.mean(psi)) if psi else 0,
            'ks_max':float(max(k.statistic for k in ks)),'ks_min_p_value':float(min(k.pvalue for k in ks)),
            'dimensions':r.shape[1],'reference_samples':len(r),'current_samples':len(x),
            'interpretation':'Distribution shift alone does not prove manipulation.'}

def activation_checks(activations,labels):
    x=np.asarray(activations,dtype=float);results=[]
    for label in sorted(set(labels)):
        idx=np.array([i for i,l in enumerate(labels) if l==label]);a=x[idx]
        if len(a)<6:results.append({'class_id':label,'available':False,'reason':'At least six class samples required'});continue
        centered=a-a.mean(axis=0);_,_,v=np.linalg.svd(centered,full_matrices=False)
        scores=(centered@v[0])**2;cluster=KMeans(n_clusters=2,random_state=47321,n_init=10).fit_predict(a)
        counts=np.bincount(cluster,minlength=2)
        results.append({'class_id':label,'available':True,'indices':idx.tolist(),'spectral_scores':scores.tolist(),
                        'cluster_membership':cluster.tolist(),'minority_fraction':float(counts.min()/len(a)),
                        'limitations':'Cluster separation is an anomaly signal, not proof of a backdoor.'})
    return results

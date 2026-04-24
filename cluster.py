from sklearn.cluster import MiniBatchKMeans

from config import RANDOM_STATE


def cluster_data(X, n_clusters):
    model = MiniBatchKMeans(n_clusters=n_clusters, random_state=RANDOM_STATE, n_init="auto")
    return model.fit_predict(X)

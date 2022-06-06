import numpy as np
from scipy.linalg import eigh, svd, qr, solve
from scipy.sparse import eye, csr_matrix
from scipy.sparse.linalg import eigsh
from geomstats.geometry.pullback_metric import PullbackMetric
from geomstats.learning.knn import KNearestNeighborsClassifier
from geomstats.geometry.euclidean import Euclidean
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from matplotlib import ticker

np.random.seed(10)

def Compute_neighbours(data, labels, metric, n_neighbors):

    knn = KNearestNeighborsClassifier(n_neighbors= n_neighbors, distance=metric.dist)
    # knn.distance = 'minkowski' # Fits according to Euclidian distance
    # knn.distanvce = metric.dist
    # knn.distance_params = None
    knn.fit(data,labels)
    k_nearest_vals = knn.kneighbors(data, return_distance=False)
    print("K-nearest values of each point:")
    print(k_nearest_vals[:3,:])
    return k_nearest_vals

def barycenter_weights(metric, X, Y, indices, reg=1e-3):
    """Compute barycenter weights of X from Y along the first axis
    We estimate the weights to assign to each point in Y[indices] to recover
    the point X[i]. The barycenter weights sum to 1.
    Parameters
    ----------
    X : array-like, shape (n_samples, n_dim)
    Y : array-like, shape (n_samples, n_dim)
    indices : array-like, shape (n_samples, n_dim)
            Indices of the points in Y used to compute the barycenter
    reg : float, default=1e-3
        amount of regularization to add for the problem to be
        well-posed in the case of n_neighbors > n_dim
    Returns
    -------
    B : array-like, shape (n_samples, n_neighbors)
    Notes
    -----
    See developers note for more information.
    """

    n_samples, n_neighbors = indices.shape
    assert X.shape[0] == n_samples

    B = np.empty((n_samples, n_neighbors), dtype=X.dtype)
    v = np.ones(n_neighbors, dtype=X.dtype)

    # this might raise a LinalgError if G is singular and has trace
    # zero
    for i, ind in enumerate(indices):
        A = Y[ind]
        C = metric.log(A,X[i])
        G = np.dot(C,C.T)
        G1 = metric.metric_matrix(C)
        trace = np.trace(G)
        if trace > 0:
            R = reg * trace
        else:
            R = reg
        G.flat[:: n_neighbors + 1] += R
        w = solve(G, v, sym_pos=True)
        B[i, :] = w / np.sum(w)
        
    return B

def Compute_W(data, metric ,k_nearest_vals, n_samples, n_neighbors ):
    B= barycenter_weights(metric, data,data,k_nearest_vals);
    indptr = np.arange(0, n_samples * n_neighbors + 1, n_neighbors)
    W = csr_matrix((B.ravel(), k_nearest_vals.ravel(), indptr), shape=(n_samples, n_samples))
    W_mat = W.toarray()
    M = eye(*W.shape, format=W.format) - W
    M = (M.T * M).toarray()
    return M , W

def Validate_W(data, W, k_nearest_vals):
    # Validate the values of the weight matrix
    linear_combos = []
    neighborhood_weights = []
    for i in range(len(data)):
        weights = W.toarray()[i][k_nearest_vals[i]]
        neighborhood = data[k_nearest_vals[i]]
        weighted_neighbors = weights.reshape(-1,1)*neighborhood
        lin_x1 = np.sum(weighted_neighbors[:,0])
        lin_x2 = np.sum(weighted_neighbors[:,1])
        lin_x3 = np.sum(weighted_neighbors[:,2])
        linear_combos.append([lin_x1, lin_x2, lin_x3])
        neighborhood_weights.append(weights)
    linear_X = np.array(linear_combos)

    fig = plt.figure(figsize=(16, 8))
    ax = fig.add_subplot(121)
    ax.scatter(linear_X[:,0], linear_X[:,2], c='red', s=50, label='Linear Reconstruction')
    ax.scatter(data[:,0], data[:,2], c='blue', s=10, label='Original Data')
    ax.set_title('Local Linear Combinations')
    ax.set_xlabel("Dimension 0")
    ax.set_ylabel("Dimension 2")
    ax.legend(loc='upper left');

    ax2 = fig.add_subplot(122)
    ax2.scatter(linear_X[:,0], linear_X[:,1], c='red', s=50, label='Linear Reconstruction')
    ax2.scatter(data[:,0], data[:,1], c='blue', s=10, label='Original Data')
    ax2.set_title('Local Linear Combinations')
    ax2.set_xlabel("Dimension 0")
    ax2.set_ylabel("Dimension 1")
    ax2.legend(loc='upper left');
    return

class Optimize_y():
    def __init__(self, M, n_samples,n_components) :
        pass
    
        self.n_dimensions = n_components
        self.n_samples = n_samples
        self.Y0 = np.random.rand(n_samples, self.n_dimensions)
        self.M = M

    def objective_function(self,Y):
        Y = np.reshape(Y,(self.n_samples, self.n_dimensions))
        return np.trace(np.matmul (np.matmul(Y.T , self.M) , Y))

    def cons1(self,y):
        y = np.reshape(y,(self.n_samples, self.n_dimensions))
        return np.sum(y ,axis = 1)

    def cons2(self,y):
        var = 0
        rotational_cons = np.zeros((np.shape(y)))
        y = np.reshape(y,(self.n_samples, self.n_dimensions))
        for i in range(self.n_samples):
            y_i = np.array(y[i,:])[np.newaxis]
            var1 = y_i.T @ y_i
            var = var + var1;
        rotational_cons = (1/ self.n_samples)*var - eye(2,2)
        aaa = np.squeeze(np.asarray(rotational_cons.reshape(4,1)))
        return aaa

    def mimimize(self):
        cons = ({'type': 'eq', 'fun': self.cons1},
                {'type': 'eq', 'fun': self.cons2}
                )
            
        a = self.objective_function(self.Y0)
        obj = minimize( self.objective_function , self.Y0 , constraints=cons)
        return obj

def null_space(M, k):
    k_skip = 1
    tol = 1e-6
    max_iter = 100
    random_state = None
    #v0 = random_state.uniform(-1, 1, M.shape[0])
    eigen_values, eigen_vectors = eigsh(
                M, k + k_skip, sigma=0.0, tol=tol, maxiter=max_iter )
    return eigen_vectors[:, k_skip:], np.sum(eigen_values[k_skip:])

def plot_3d(points, points_color, title):
    x, y, z = points.T

    fig, ax = plt.subplots(
        figsize=(8, 8),
        facecolor="white",
        tight_layout=True,
        subplot_kw={"projection": "3d"},
    )
    fig.suptitle(title, size=16)
    col = ax.scatter(x, y, z, c=points_color, s=50, alpha=0.8)
    ax.view_init(azim=-60, elev=9)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.zaxis.set_major_locator(ticker.MultipleLocator(1))

    fig.colorbar(col, ax=ax, orientation="horizontal", shrink=0.6, aspect=60, pad=0.01)
    plt.show()


def plot_2d(points, points_color, title):
    fig, ax = plt.subplots(figsize=(8, 8), facecolor="white", constrained_layout=True)
    fig.suptitle(title, size=16)
    add_2d_scatter(ax, points, points_color)
    plt.show()


def add_2d_scatter(ax, points, points_color, title=None):
    x, y = points.T
    ax.scatter(x, y, c=points_color, s=50, alpha=0.8)
    ax.set_title(title)
    ax.xaxis.set_major_formatter(ticker.NullFormatter())
    ax.yaxis.set_major_formatter(ticker.NullFormatter())

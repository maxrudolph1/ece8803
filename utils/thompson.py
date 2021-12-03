import numpy as np


class ThompsonSampling:
    def __init__(self, n_arms, alphas, betas):
        self.n_arms = n_arms
        self.alphas = alphas
        self.betas = betas
        self.means = np.zeros((self.n_arms,))

    def select_arm(self):
        cur_means = [np.random.beta(self.alphas[i], self.betas[i]) for i in range(self.n_arms)]
        return np.argmax(cur_means)

    def register_success(self, arm):
        self.alphas[arm] += 1

    def register_failure(self, arm):
        self.betas[arm] += 1

    def results(self):
        sample_means = np.array(self.alphas)/ ( np.array(self.alphas) + np.array(self.betas))
        return sample_means
def main():
    thomp = ThompsonSampling(3, [5, 1, 10], [1, 4, 10])

    true_means = [0.8, 0.1, 0.4]

    for i in range(1000):
        arm = thomp.select_arm()

        success = np.random.random() < true_means[arm]

        if success:
            thomp.register_success(arm)
        else:
            thomp.register_failure(arm)
    print(thomp.results())

if __name__=='__main__':
    main()
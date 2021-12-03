import numpy as np


class ThompsonSampling:
    def __init__(self, n_arms, prior_success, prior_fails, dist='beta'):
        self.n_arms = n_arms
        self.prior_success = np.array(prior_success)
        self.prior_fails = np.array(prior_fails)
        self.observed_success = np.zeros((self.n_arms))
        self.observed_failure = np.zeros((self.n_arms))
        self.arm_pulled = np.zeros((self.n_arms))
        self.means = np.zeros((self.n_arms,))
        self.dist = dist

    def select_arm(self):
        if self.dist == 'beta':
            cur_means = [np.random.beta(self.prior_success[i] + self.observed_success[i], self.prior_fails[i] + self.observed_failure[i]) for i in range(self.n_arms)]
        elif self.dist == 'triangle':
            mode = (self.prior_success + self.observed_success)/ (self.prior_success + self.observed_success+ self.prior_fails + self.observed_failure) 
            cur_means = [np.random.triangular(0,mode[i], 1) for i in range(self.n_arms)]
        elif self.dist == 'normal':
            mean = (self.prior_success + self.observed_success)/ (self.prior_success + self.observed_success+ self.prior_fails + self.observed_failure)
            var = np.exp(-1/(self.prior_success + self.observed_success + self.prior_fails + self.observed_failure))
            cur_means  = np.clip([np.random.normal(loc=mean[i],scale=var[i]) for i in range(self.n_arms)], 0,1)

        return np.argmax(cur_means)

    def register_success(self, arm):
        self.observed_success[arm] += 1
        self.arm_pulled[arm] += 1

    def register_failure(self, arm):
        self.observed_failure[arm] += 1
        self.arm_pulled[arm] += 1

    def get_sample_means(self):
        sample_means = (self.observed_success)/ (self.observed_success + self.observed_failure + 1)
        return sample_means

    def prior_sample_means(self):
        sample_means = (self.prior_success + self.observed_success)/ (self.prior_success + self.observed_success+ self.prior_fails + self.observed_failure) 
        return sample_means

    

def main():
    thomp = ThompsonSampling(3, [1, 1, 10], [1, 4, 10], dist='normal')

    true_means = [0.8, 0.1, 0.4]

    for i in range(1000):
        arm = thomp.select_arm()

        success = np.random.random() < true_means[arm]

        if success:
            thomp.register_success(arm)
        else:
            thomp.register_failure(arm)
    print(thomp.sample_means())

if __name__=='__main__':
    main()
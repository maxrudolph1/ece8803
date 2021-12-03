import numpy as np
import caption_contest_data as ccd
from utils.experiment import Experiment
from utils.thompson import ThompsonSampling
from matplotlib import pyplot as plt
big_prior_idx = np.array([554, 564, 568, 570, 573, 575, 578, 580, 583, 585, 587, 590, 595,
                          598, 602, 604, 607, 609, 611, 613, 615, 617, 619, 621, 624, 626,
                          628, 630, 632, 634, 662, 665, 667, 669, 671, 673, 675, 677, 679,
                          681, 683, 685, 687, 689, 691])
big_prior_idx = big_prior_idx[:2]



results = {}

for prior_idx in big_prior_idx:

    df = ccd.summary(prior_idx).query('rank <= 10')
    true_means = np.array(df['funny']) / (np.array(df['funny']) + np.array(df['unfunny'])) 
    prior_means = np.array(df['funny']) / (np.array(df['funny']) + np.array(df['unfunny'])) + \
                    np.array([np.random.triangular(-np.min(true_means), 0, (1 - np.max(true_means))) for i in range(10)])
    prior_succ = np.round(prior_means * 100)
    prior_fail = np.round((1 - prior_means) * 100)

    exp = Experiment(num_arms=true_means.shape[0], true_means=true_means, prior_succ=prior_succ, prior_fail=prior_fail, dist='normal',
                 trials=10000)

    results[prior_idx] = exp.run_experiment()
    


for res in results.keys():
    print('---------------------')
    print(results[res]['opt_arm'])
    print(results[res]['true_opt_arm'])
    print(results[res]['sample_means'])
    print(results[res]['N_pulled'])

plt.show(block=False)
plt.pause(0.001) # Pause for interval seconds.
input("hit[enter] to end.")
plt.close('all') 
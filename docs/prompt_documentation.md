# Prompt Documentation

## Phase 1 - Problem Exploration and Selection

### Goal

Explore all available problem statements, compare them using different metrics, and select the best
one for implementation within the 48-hour hackathon.

---

### Prompt 1

```
gave the screen shots of presentation based on these 4 problem sets what
questions can be asked

https://societegenerale.iamneo.ai/pb-5-grc-exception-policy-waiver-management/
https://societegenerale.iamneo.ai/third-party-vendor-risk-management/
https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/
https://societegenerale.iamneo.ai/identity-sprawl-privileged-access-abuse-detection-in-hybrid-enterprises/
```

**Purpose:** Generate questions to ask the presenters after reviewing the problem statement slides.

---

### Prompt 2

```
This is the detailed flyer given by the Société general for the hackathon.
Add on these to the analysis in the previous chat. and also look at the three
options for the solutions and consider its extended highlight feature we can
implement.

Analyse these and give me the best problem set which is achievable in the time
frame. I will be using claude code with pro subscription so consider it. The
data simulation is the main challenge consider it also.

Rate and compare on several categories including judges perspective and earlier
categories.

Search for the datasets already available, in every place from huggingface to
opendata.

reanalyse on your own metrics do not consider the earlier metrics
```

**Purpose:** Perform an overall comparison while considering feasibility, datasets, judges' perspective,
and available tooling.

---

### Prompt 3

```
How should i implement this. any public datasets available
```

**Purpose:** Explore implementation ideas and available public datasets.

---

### Prompt 4

```
These are the 4 praoblem sets provided by the Socite general , ihackmyplace
campus hackathon for rvce.

we have been provided with these problem sets and need to find a solution mvp
within 48 hours,

explore the problem set and exaplain problem set one by one as i say,
cover the background research. why it is needed, who are the stakeholders, how
this will impact, whats the business impact, what are the ways we can approach
the problem to find a solution beyond winning, give the resources and links to
do further research.

lets start with one
```

**Purpose:** Perform detailed background research on each problem statement.

---

### Prompt 5

```
Analysis: Make several criteria's to rank these problem sets. Some of which can
be difficulty, business impact, demo and deployment and other standard used
metrics in the development of the solutions.

also consider the fact that Société Générale is the one valuating these
solutions and how likable the solution will be for judges.

The data structure will be provided but we need to generate the data and the
cases.

Compare them based on the analysis.
```

**Purpose:** Create a structured evaluation framework for comparing the problems.

---

### Prompt 6

```
https://societegenerale.iamneo.ai/pb-5-grc-exception-policy-waiver-management/
https://societegenerale.iamneo.ai/third-party-vendor-risk-management/
https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/
https://societegenerale.iamneo.ai/identity-sprawl-privileged-access-abuse-detection-in-hybrid-enterprises/

each problemset is contained in each url
now they have given proper extended problem sets and the possible solutions.
on these new updates data now make the same classification and compare the
problem sets.

Ask me if there are any doubts.
```

**Purpose:** Re-run the comparison using the updated official descriptions.

---

### Prompt 7

```
there are 3 options to solve each problem see all, we will need to do something
beyond the advanced to grab attentions
```

**Purpose:** Brainstorm enhancements beyond the official solution options.

---

### Prompt 8

```
https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/

more about this

here in the option a) they have given difficulty of 5/5 can you explain that.
and whats the businees impact score you would give it.
Note that is one of the problem sets provided by the societe generale 48hours
hackathon
```

**Purpose:** Understand the complexity and business value of Problem Statement 3.

---

### Prompt 9

```
analyse with same thing for this problem set [3rd ps]
```

**Purpose:** Continue detailed analysis of Problem Statement 3.

---

### Prompt 10

```
Now do the comparative study and which is better to take as a problem set for
hackathon
```

**Purpose:** Decide the best problem statement to choose.

---

### Prompt 11

```
Similarly analyse this and do the comparative analysis [4th ps]
```

**Purpose:** Compare the remaining problem statements using the same methodology.

---

### Prompt 12

```
no I meant adding some of the features of option b and c to a and building a wow
factor to it.
also for ml (ps 3 and ps 4), is there any thing i can use from newer
implementations as transformers or different architecture
```

**Purpose:** Explore advanced features and modern ML architectures.

---

### Prompt 13

```
ask me some of the questions so that you could suggest me the correct problem
set
```

**Purpose:** Refine the recommendation based on team capabilities.

---

### Prompt 14

```
i am leaning more towards 3rd problem set, so what should i know to build this
and is the business impact high for this
```

**Purpose:** Validate the choice of Problem Statement 3.

---

### Prompt 15

```
i know basic graph knowledge, If it were you to build the synthetic data how
would you do it
```

**Purpose:** Plan synthetic data generation.

---

### Prompt 16

```
is there any huggingface datasets which can take some of the feilds from
```

**Purpose:** Find reusable public datasets.

---

### Prompt 17

```
In the options A and B, I want to approact it like combining backend engineer
skills with the approach A(ML Engineer).
How would you tackle it
```

**Purpose:** Design a hybrid backend + ML implementation strategy.

---

### Prompt 18

```
I am choosing Ephemeral Cloud problem, so once again analyse the deliverables
with success criteria and data structure descriptions
```

**Purpose:** Understand deliverables and expected outputs.

---

### Prompt 19

```
Create single analysis file by compiling all the learing into a single file on
problem set 3 Ephemeral Cloud problem and export it.
It should include all the analysis you have done till now on that problem set
```

**Purpose:** Consolidate all research into one reference document.

---

### Prompt 20

```
Can we build a real time api of the data for this anomaly soluiton of Ephemeral
Cloud
```

**Purpose:** Explore real-time streaming and API integration.

---

### Prompt 21

```
According to the given problem statement what are they expecting and what will
be the wow factor
```

**Purpose:** Understand judging expectations and differentiating features.

---

### Prompt 22

```
we have choosed the third problem set. lets plan how we can overcome this
problem what should be the flow of the problem
```

**Purpose:** Plan the end-to-end implementation flow.

---

### Prompt 23

```
give me the detailed MD of analysis and flow of the this problem, option A with
extra beyond winning.
```

**Purpose:** Generate detailed planning documentation.

---

### Prompt 24

```
[used data_resource_research.md as prompt to create dataset]
```

**Purpose:** Use prior research to guide synthetic dataset creation.

---

### Prompt 25

```
We need to create a scaffold of project folder structure.
make proper structured folder tree according to the flow of the project and name
it properly with subfolders. add gitkeep for the folders
organise the current files in the respective folders.
ask quesiton if needed
```

**Purpose:** Create a clean project structure.

---

### Prompt 26

```
make a context.md as single source of truth of progress,
it should contain everything about what happend, when, why, and flow and
progress,
it should be like when a new ai session start by reading this md it should get
the complete context of what has happend.
also update the claude.md
context.md should be updated after every conversation
```

**Purpose:** Maintain project continuity and documentation across AI sessions.

---

## Result of this phaseyhxplored all four hackathon problem statements.

- Performed multiple rounds of comparative analysis.
- Researched datasets and synthetic data strategies.
- Evaluated implementation feasibility and judge appeal.
- Planned enhancements beyond the baseline solutions.
- Selected **Problem Statement 3 – Ephemeral Cloud Kubernetes Resource Risk Detection** as the
  final project.

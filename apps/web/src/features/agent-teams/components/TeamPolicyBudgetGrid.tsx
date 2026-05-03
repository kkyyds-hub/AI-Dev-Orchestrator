import type { BudgetPolicy, TeamPolicy } from "../types";
import { BudgetPolicyEditorCard } from "./BudgetPolicyEditorCard";
import { TeamPolicyEditorCard } from "./TeamPolicyEditorCard";

export function TeamPolicyBudgetGrid(props: {
  teamPolicy: TeamPolicy;
  budgetPolicy: BudgetPolicy;
  onChangeTeamPolicy: (policy: TeamPolicy) => void;
  onChangeBudgetPolicy: (policy: BudgetPolicy) => void;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-2">
      <TeamPolicyEditorCard
        policy={props.teamPolicy}
        onChange={props.onChangeTeamPolicy}
      />
      <BudgetPolicyEditorCard
        policy={props.budgetPolicy}
        onChange={props.onChangeBudgetPolicy}
      />
    </section>
  );
}

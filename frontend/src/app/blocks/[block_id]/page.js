import IdeaPage from '@/components/pages/IdeaPage';
import ConceptPage from '@/components/pages/ConceptPage';
import MoonshotPage from '@/components/pages/MoonshotPage';
import NeedsPage from '@/components/pages/NeedsPage';
import OpportunityPage from '@/components/pages/OpportunityPage';
import OutcomePage from '@/components/pages/OutcomePage';
import PossibilityPage from '@/components/pages/PossibilityPage';
import ProblemPage from '@/components/pages/ProblemPage';
import NotFoundPage from '@/app/not-found';


const blockPages = {
    concept_block: ConceptPage,
    idea_block: IdeaPage,
    moonshot_block: MoonshotPage,
    needs_block: NeedsPage,
    opportunity_block: OpportunityPage,
    outcome_block: OutcomePage,
    possibility_block: PossibilityPage,
    problem_block: ProblemPage,
};

export default function Page({ params }) {
    const { block_id } = params;
    const SelectedPage = blockPages[block_id] || <NotFoundPage  message="Block Page Not Found"/>; 
    return <SelectedPage />;
}
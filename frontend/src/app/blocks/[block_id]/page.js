import IdeaPage from '@/components/pages/IdeaPage';
// import ConceptPage from '@/components/pages/ConceptPage';
// import MoonshotPage from '@/components/pages/MoonshotPage';
// import NeedsPage from '@/components/pages/NeedsPage';
// import OpportunityPage from '@/components/pages/OpportunityPage';
// import OutcomePage from '@/components/pages/OutcomePage';
// import PossibilityPage from '@/components/pages/PossibilityPage';
import ProblemPage from '@/components/pages/ProblemPage';
import GeneralChatPage from '@/components/pages/GeneralChatPage';
import NotFoundPage from '@/app/not-found';


const blockPages = {
    // concept: ConceptPage,
    idea: IdeaPage,
    // moonshot: MoonshotPage,
    // needs: NeedsPage,
    // opportunity: OpportunityPage,
    // outcome: OutcomePage,
    // possibility: PossibilityPage,
    problem: ProblemPage,
    general: GeneralChatPage,
};

export default function Page({ params }) {
    const { block_id } = params;
    const SelectedPage = blockPages[block_id] || <NotFoundPage  message="Block Page Not Found"/>; 
    return <SelectedPage />;
}
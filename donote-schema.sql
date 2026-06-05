--
-- PostgreSQL database dump
--

\restrict ScX3OJ6Z6nyWKbgWCcnhf8qaubvvzbSfMSPtqfjFfLbnxaRiiiS8FKqD5xWJQPB

-- Dumped from database version 17.9
-- Dumped by pg_dump version 17.9

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: category_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.category_type AS ENUM (
    'INCOME',
    'EXPENSE'
);


ALTER TYPE public.category_type OWNER TO postgres;

--
-- Name: goal_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.goal_status AS ENUM (
    'IN_PROGRESS',
    'ACHIEVED',
    'EXPIRED',
    'CANCELLED'
);


ALTER TYPE public.goal_status OWNER TO postgres;

--
-- Name: participant_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.participant_status AS ENUM (
    'PENDING',
    'SETTLED'
);


ALTER TYPE public.participant_status OWNER TO postgres;

--
-- Name: settlement_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.settlement_status AS ENUM (
    'PENDING',
    'COMPLETED',
    'CANCELLED'
);


ALTER TYPE public.settlement_status OWNER TO postgres;

--
-- Name: split_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.split_type AS ENUM (
    'EQUAL',
    'CUSTOM'
);


ALTER TYPE public.split_type OWNER TO postgres;

--
-- Name: transaction_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.transaction_type AS ENUM (
    'INCOME',
    'EXPENSE'
);


ALTER TYPE public.transaction_type OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: budgets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.budgets (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    year_month character varying(7) NOT NULL,
    category_id uuid,
    amount numeric(12,0) NOT NULL,
    is_warning_notified boolean DEFAULT false NOT NULL,
    is_exceeded_notified boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_budget_amount_gt_zero CHECK ((amount > (0)::numeric)),
    CONSTRAINT ck_budget_year_month_format CHECK (((year_month)::text ~ '^\d{4}-\d{2}$'::text))
);


ALTER TABLE public.budgets OWNER TO postgres;

--
-- Name: categories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.categories (
    id uuid NOT NULL,
    user_id uuid,
    name character varying(50) NOT NULL,
    type public.category_type NOT NULL
);


ALTER TABLE public.categories OWNER TO postgres;

--
-- Name: goals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.goals (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    target_amount numeric(12,0) NOT NULL,
    target_date date,
    category_id uuid NOT NULL,
    description character varying(500),
    status public.goal_status NOT NULL,
    created_at timestamp without time zone NOT NULL,
    achieved_at timestamp without time zone,
    is_achieved_notified boolean DEFAULT false NOT NULL,
    is_25_notified boolean DEFAULT false NOT NULL,
    is_50_notified boolean DEFAULT false NOT NULL,
    is_75_notified boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_goal_target_amount_gt_zero CHECK ((target_amount > (0)::numeric))
);


ALTER TABLE public.goals OWNER TO postgres;

--
-- Name: import_hashes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.import_hashes (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    hash character varying(64) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.import_hashes OWNER TO postgres;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    type character varying(50) NOT NULL,
    message character varying(255) NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.notifications OWNER TO postgres;

--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.refresh_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token character varying(500) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.refresh_tokens OWNER TO postgres;

--
-- Name: settlement_participants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.settlement_participants (
    id uuid NOT NULL,
    settlement_id uuid NOT NULL,
    user_id uuid,
    display_name character varying(20) NOT NULL,
    amount numeric(12,0) NOT NULL,
    status public.participant_status DEFAULT 'PENDING'::public.participant_status NOT NULL,
    settled_at timestamp without time zone,
    CONSTRAINT ck_settlement_participant_amount_ge_zero CHECK ((amount >= (0)::numeric))
);


ALTER TABLE public.settlement_participants OWNER TO postgres;

--
-- Name: settlements; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.settlements (
    id uuid NOT NULL,
    transaction_id uuid NOT NULL,
    creator_id uuid NOT NULL,
    total_amount numeric(12,0) NOT NULL,
    split_type public.split_type NOT NULL,
    status public.settlement_status DEFAULT 'PENDING'::public.settlement_status NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.settlements OWNER TO postgres;

--
-- Name: transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transactions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    type public.transaction_type NOT NULL,
    amount numeric(12,0) NOT NULL,
    category_id uuid NOT NULL,
    description character varying(500),
    transaction_date date NOT NULL,
    transaction_time time without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_transaction_amount_gt_zero CHECK ((amount > (0)::numeric))
);


ALTER TABLE public.transactions OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: budgets budgets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: goals goals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_pkey PRIMARY KEY (id);


--
-- Name: import_hashes import_hashes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_hashes
    ADD CONSTRAINT import_hashes_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_key UNIQUE (token);


--
-- Name: settlement_participants settlement_participants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlement_participants
    ADD CONSTRAINT settlement_participants_pkey PRIMARY KEY (id);


--
-- Name: settlements settlements_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlements
    ADD CONSTRAINT settlements_pkey PRIMARY KEY (id);


--
-- Name: settlements settlements_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlements
    ADD CONSTRAINT settlements_transaction_id_key UNIQUE (transaction_id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: budgets uq_budget_user_month_category; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT uq_budget_user_month_category UNIQUE (user_id, year_month, category_id);


--
-- Name: categories uq_category_user_name_type; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT uq_category_user_name_type UNIQUE (user_id, name, type);


--
-- Name: import_hashes uq_import_hashes_user_hash; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_hashes
    ADD CONSTRAINT uq_import_hashes_user_hash UNIQUE (user_id, hash);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_goals_user_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_goals_user_category ON public.goals USING btree (user_id, category_id);


--
-- Name: ix_notifications_user_is_read; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notifications_user_is_read ON public.notifications USING btree (user_id, is_read);


--
-- Name: ix_settlement_participants_settlement_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_settlement_participants_settlement_id ON public.settlement_participants USING btree (settlement_id);


--
-- Name: ix_settlements_creator_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_settlements_creator_id ON public.settlements USING btree (creator_id);


--
-- Name: ix_settlements_transaction_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_settlements_transaction_id ON public.settlements USING btree (transaction_id);


--
-- Name: ix_transactions_category_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_transactions_category_id ON public.transactions USING btree (category_id);


--
-- Name: ix_transactions_user_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_transactions_user_date ON public.transactions USING btree (user_id, transaction_date);


--
-- Name: uq_budget_overall; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_budget_overall ON public.budgets USING btree (user_id, year_month) WHERE (category_id IS NULL);


--
-- Name: uq_settlement_participant_user; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_settlement_participant_user ON public.settlement_participants USING btree (settlement_id, user_id) WHERE (user_id IS NOT NULL);


--
-- Name: budgets budgets_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: budgets budgets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: categories categories_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: goals goals_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: goals goals_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.goals
    ADD CONSTRAINT goals_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: import_hashes import_hashes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.import_hashes
    ADD CONSTRAINT import_hashes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: settlement_participants settlement_participants_settlement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlement_participants
    ADD CONSTRAINT settlement_participants_settlement_id_fkey FOREIGN KEY (settlement_id) REFERENCES public.settlements(id) ON DELETE CASCADE;


--
-- Name: settlement_participants settlement_participants_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlement_participants
    ADD CONSTRAINT settlement_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: settlements settlements_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlements
    ADD CONSTRAINT settlements_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public.users(id);


--
-- Name: settlements settlements_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.settlements
    ADD CONSTRAINT settlements_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: transactions transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict ScX3OJ6Z6nyWKbgWCcnhf8qaubvvzbSfMSPtqfjFfLbnxaRiiiS8FKqD5xWJQPB


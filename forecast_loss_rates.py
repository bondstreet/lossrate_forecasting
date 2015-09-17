"""
Sub calculate_dollar_loss()
    Dim BAD_RATE_DISPLACE As Integer
    BAD_RATE_DISPLACE = 13
    'iterate through bad rate table to calculate each cell's dollar loss
    Dim PERIODS As Integer 'number of periods in a year
    PERIODS = 4
    
    'set up amortization curves. hard coded for now. optimally, would be calculated on the fly...
    'one indexing everything to signify actual time periods
    Dim amort_curves(3, 12) As Double
    amort_curves(1, 1) = 0.7629
    amort_curves(1, 2) = 0.5174
    amort_curves(1, 3) = 0.2632
    amort_curves(1, 4) = 0
    
    amort_curves(2, 1) = 0.8897
    amort_curves(2, 2) = 0.7755
    amort_curves(2, 3) = 0.6572
    amort_curves(2, 4) = 0.5347
    amort_curves(2, 5) = 0.408
    amort_curves(2, 6) = 0.2767
    amort_curves(2, 7) = 0.1407
    amort_curves(2, 8) = 0
    
    amort_curves(3, 1) = 0.9317
    amort_curves(3, 2) = 0.8609
    amort_curves(3, 3) = 0.7877
    amort_curves(3, 4) = 0.7118
    amort_curves(3, 5) = 0.6333
    amort_curves(3, 6) = 0.552
    amort_curves(3, 7) = 0.4678
    amort_curves(3, 8) = 0.3807
    amort_curves(3, 9) = 0.2904
    amort_curves(3, 10) = 0.1969
    amort_curves(3, 11) = 0.1002
    amort_curves(3, 12) = 0
    
    'Parameter assumptions
    RECOVERY_RATE = 0.1
    
    START_COL = 4
    For term_num = 1 To 3
        For r = 17 To 25
            For c = START_COL To (START_COL + 6)
                bad_rate = Cells(r - BAD_RATE_DISPLACE, c).Value
                periodic_bad_rate = bad_rate / (PERIODS * term_num) 'split the bads evenly across the number of periods
                bad_sum = 0
                For i = 1 To (PERIODS * term_num)
                    If i = 1 Then
                        previous_principal = 1
                    Else
                        previous_principal = amort_curves(term_num, (i - 1))
                    End If
                    average_principal = (previous_principal + amort_curves(term_num, i)) / 2 'take the average of current remaining principal, and previously remaining principal, because we don't know exaclty when bads happen over a quarter
                    period_bad = periodic_bad_rate * average_principal * (1 - RECOVERY_RATE)
                    bad_sum = bad_sum + period_bad
                Next i
                bad_sum = Format(bad_sum, "Percent")
                Cells(r, c).Value = bad_sum
            Next c
        Next r
        START_COL = START_COL + 6 + 4 + 1
    Next term_num
    
End Sub

"""
from pandas import DataFrame, Series
import ipdb
from amortization import Loan

# annual incidence curves tell you b/w time t and t-1, what proportion of the bad portfolio goes bad
ANNUAL_INCIDENCE_CURVES = {
	3:Series([.233, .367, .40], index=[1,2,3]),
	2:Series([.388, .612], index=[1,2]),
	1:Series([1.0], index=[1])
}

BADRATE_DIR = 'badrate_tables'
LOSSRATE_DIR = 'lossrate_tables'

def get_amortized_balance_curve(interest_rate, term, periods_per_year):
	"""
		Return a Series of remaining balance at each period in time for a fully amortized loan with the inputs.
	"""
	loan = Loan(interest_rate/periods_per_year, term*periods_per_year, 1)
	balance_curve = {}
	period_count = 1
	for period in loan.schedule():
		balance = period.balance
		balance_curve[period_count] = balance
		period_count += 1
	balance_curve = Series(balance_curve)
	return balance_curve

def get_incidence_curves(term, periods_per_year):
	"""
		Returns a Series representing what proportion of the bad portfolio goes bad b/w time t and t-1, where t are periods according to the input periods_per_year
	"""
	annual_incidence_curve = ANNUAL_INCIDENCE_CURVES[term]
	new_index = []
	new_incidence = []
	index_count = 1
	for i in annual_incidence_curve.index:
		annual_incidence = annual_incidence_curve[i]
		# evenly allocate annual incidence across year
		for n in range(periods_per_year):
			new_index.append(index_count)
			new_incidence.append(annual_incidence/periods_per_year)
			index_count += 1 
	return Series(new_incidence, index=new_index)

def forecast_loss_rates_from_bad_rates(bad_rate_csv, term, avg_interest_rate=.14, recovery_rate=0.1, periods_per_year=24):
	"""
		Given an input of a csv of a smoothed bad rate table, spits out forecasted loss rate table in a csv
	"""
	# read bad rates
	bad_rate_df = DataFrame.from_csv(bad_rate_csv)
	orig_cols = bad_rate_df.columns
	orig_rows = bad_rate_df.index
	# calculate amortization curve, given term, avg interest rate, avg loan size
	balance_curve = get_amortized_balance_curve(avg_interest_rate, term, periods_per_year)
	# calculate "incidence curve" (hard coded for now); straight line for 1 year term
	incidence_curve = get_incidence_curves(term, periods_per_year)
	
	data = {}
	# for each cell in the bad rate table
	for col in bad_rate_df.columns:
		new_row = {}
		for row in bad_rate_df.index:
			# get current bad rate
			cur_bad_rate = bad_rate_df[col][row]
			# keep track of cumulative principal lost
			bad_sum = 0
			# for each period
			for period_count in range(1, (term*periods_per_year)+1):
				# calculate periodic bad rate: split bads according to an "incidence curve"
				periodic_bad_rate = cur_bad_rate * incidence_curve[period_count]
				# get previous principal on principal/balance curve
				if period_count == 1:
					previous_balance = 1
				else:
					previous_balance = balance_curve[period_count-1]
				# get current principal on principal/balance curve
				current_balance = balance_curve[period_count]
				# calculate average
				average_balance = (previous_balance + current_balance) / 2.
				# multiply by this period's bad rate
				# multiply by (1-recovery rate)
				cur_bad = average_balance * periodic_bad_rate * (1-recovery_rate)
				# result represents principal lost this period, add it to the counter
				bad_sum += cur_bad
			new_row[row] = bad_sum
		data[col] = new_row
	return DataFrame(data).reindex(columns=orig_cols, index=orig_rows)


